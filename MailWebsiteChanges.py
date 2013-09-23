#!/usr/bin/python

import urllib2
from lxml import etree
import re
import StringIO

import smtplib
from email.mime.text import MIMEText
from email.header import Header
from urlparse import urljoin

import os.path
import sys

import time
from time import strftime


import config

defaultEncoding = 'utf-8'
emptyfeed = u'<rss version="2.0"><channel><title>MailWebsiteChanges Feed</title><link>https://github.com/Debianguru/MailWebsiteChanges</link><description>The MailWebsiteChanges Feed</description></channel></rss>'


def parseSite(uri, contenttype, xpathquery, regex, enc):
        content, warning = None, None

        try:
                if xpathquery == '':
                        file = urllib2.urlopen(uri)
                        content = [file.read().decode(enc).encode(defaultEncoding)]
                        file.close()
                else:
                        if contenttype == 'xml':
                                parser = etree.XMLParser(recover=True, encoding=enc)
                        else:
                                parser = etree.HTMLParser(encoding=enc)

                        file = urllib2.urlopen(uri)
                        tree = etree.parse(file, parser)
                        file.close()
                        result = tree.xpath(xpathquery)

                        if len(result) == 0:
                                warning = "WARNING: selector became invalid!"
                        else:
                                content = [etree.tostring(s).decode(enc).encode(defaultEncoding) for s in result]
        except IOError as e:
                warning = 'WARNING: could not open URL; maybe content was moved?\n\n' + str(e)
                return {'content': content, 'warning': warning}

        if regex != '':
                newcontent = []
                for c in content:
                        newcontent.extend(re.findall(r'' + regex, c))
                content = newcontent
                if len(content) == 0:
                        warning = "WARNING: regex became invalid!"

        return {'content': content, 'warning': warning}


def genFeedItem(subject, content, link, change):
        feeditem = etree.Element('item')
        titleitem = etree.Element('title')
        titleitem.text = subject + ' #' + str(change)
        feeditem.append(titleitem)
        linkitem = etree.Element('link')
        linkitem.text = link
        feeditem.append(linkitem)
        descriptionitem = etree.Element('description')
        descriptionitem.text = content
        feeditem.append(descriptionitem)
        #guiditem = etree.Element('guid')
        #guiditem.text = subject + ' - ' + strftime("%b %d %Y %H:%M:%S", time.localtime()) + ' #' + str(change)
        #feeditem.append(guiditem)
        dateitem = etree.Element('pubDate')
        dateitem.text = strftime("%a, %d %b %Y %H:%M:%S %Z", time.localtime())
        feeditem.append(dateitem)

        return feeditem


def sendmail(subject, content, sendAsHtml, link):
        if sendAsHtml:
                baseurl = None
                if link != None:
                        content = u'<p><a href="' + link + '">' + subject + u'</a></p>\n' + content
                        baseurl = urljoin(link, '/')
                mail = MIMEText('<html><head><title>' + subject + '</title>' + ('<base href="' + baseurl + '">' if baseurl else '') + '</head><body>' + content + '</body></html>', 'html', defaultEncoding)
        else:
                if link != None:
                        content = link + u'\n\n' + content
                mail = MIMEText(content, 'text', defaultEncoding)

        mail['From'] = config.sender
        mail['To'] = config.receiver
        mail['Subject'] = Header(subject, defaultEncoding)

        s = smtplib.SMTP(config.smtptlshost, config.smtptlsport)
        s.ehlo()
        s.starttls()
        s.login(config.smtptlsusername, config.smtptlspwd)
        s.sendmail(config.sender, config.receiver, mail.as_string())
        s.quit()


def pollWebsites():

        if config.rssfile != '':
                if os.path.isfile(config.rssfile):
                        feedXML = etree.parse(config.rssfile)
                else:
                        feedXML = etree.parse(StringIO.StringIO(emptyfeed))

        for site in config.sites:

                fileContent = None

                print 'polling site [' + site['shortname'] + '] ...'
                parseResult = parseSite(site['uri'], site['type'], site['xpath'], site['regex'], site['encoding'])

                if parseResult['warning']:
                        subject = '[' + site['shortname'] + '] WARNING'
                        print 'WARNING: ' + parseResult['warning']
                        if config.receiver != '':
                                sendmail(subject, parseResult['warning'], False, None)
                else:
                        i = 0
                        changes = 0
                        for content in parseResult['content']:
                                if os.path.isfile(site['shortname'] + '.' + str(i) + '.txt'):
                                        file = open(site['shortname'] + '.' + str(i) + '.txt', 'r')
                                        fileContent = file.read()
                                        file.close()

                                if content != fileContent:
                                        changes += 1

                                        file = open(site['shortname'] + '.' + str(i) + '.txt', 'w')
                                        file.write(content)
                                        file.close()

                                        subject = '[' + site['shortname'] + '] ' + config.subjectPostfix
                                        if config.receiver != '':
                                                sendmail(subject, content, (site['xpath'] != ''), site['uri'])

                                        if config.rssfile != '':
                                                feedXML.xpath('//channel')[0].append(genFeedItem(subject, content, site['uri'], changes))

                                i += 1

                        if changes > 0:
                                print '        ' + str(changes) + ' updates'
 

        if config.rssfile != '':
                for o in feedXML.xpath('//channel/item[position()<last()-' + str(config.maxFeeds - 1) + ']'):
                        o.getparent().remove(o)
                file = open(config.rssfile, 'w')
                file.write(etree.tostring(feedXML))
                file.close()


if __name__ == "__main__":
        try:
                pollWebsites()
        except:
                msg = '\n\n'.join(map(str,sys.exc_info()))
                print msg
                if config.receiver != '':
                        sendmail('[MailWebsiteChanges] Something went wrong ...', msg, False, None)

