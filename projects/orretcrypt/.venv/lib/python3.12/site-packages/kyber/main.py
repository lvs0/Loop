#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os, sys, re
import codecs

import argparse
import getpass

import xmlrpclib
import requests

import zipfile

from parsers import html, pageindex

import webbrowser
import urlparse, urllib
from bs4 import BeautifulSoup

def from_scriptroot(filename):
    currentpath = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(currentpath,filename)

def create_dir(path):
    if not os.path.exists(path):
            os.makedirs(path)


def download_file(url, auth):
    local_filename = url.split('/')[-1]

    with open(local_filename, 'wb') as f:
        print "Downloading from: %s" % (url)
        r = requests.get(url, auth=auth, stream=True)
        total_length = r.headers.get('content-length')

        if total_length is None:
            f.write(r.content)
        else:
            dl = 0
            total_length = int(total_length)
            for data in r.iter_content(chunk_size=4096):
                dl += len(data)
                f.write(data)
                done = int(50 * dl / total_length)
                sys.stdout.write("\r[%s%s]" % ('=' * done, ' ' * (50 - done)) )
                sys.stdout.flush()

    sys.stdout.write(" -> %s\n" % (local_filename) )
    return local_filename


def export_space(url, key):
    proxy = xmlrpclib.ServerProxy(url+"/rpc/xmlrpc")
    
    user = raw_input("Enter Confluence username: ")
    passwd = getpass.getpass("Enter Confluence password: ")
    auth = (user, passwd)

    token = proxy.confluence2.login(user,passwd)
    
    space = proxy.confluence2.getSpace(token, key) 
    print "Exporting space: %s Key: %s" % (space['name'], space['key'])
    spaceurl = proxy.confluence2.exportSpace(token,key,"TYPE_HTML")

    proxy.confluence2.logout(token)

    return download_file(spaceurl, auth)

def unzip_space(filename):

    print "Verifying %s" % (filename)
    z = zipfile.ZipFile(filename,'r')
    z.testzip()
    z.extractall()
    z.close()

def write_last(text):
    f = open('last','w')
    f.write(text)
    f.close()

def read_last():
    f = open('last','r')
    text = f.read()
    f.close()
    return text

def console():
    parser = argparse.ArgumentParser(description='Export a Confluence Space')

    parser.add_argument('-u','--url', nargs=1, metavar='URL', help='Download space first from server URL')
    parser.add_argument('-s','--space', nargs=1, metavar='SPACE', required=True, help='Space key')
    parser.add_argument('--single-page', action='store_true', help='Render output to single page (auto-set by --pdf)')
    parser.add_argument('--pdf', action='store_true', help='Render output to PDF')
    parser.add_argument('--toc', action='store_true', help='Add table of contents to single-page document')

    args = parser.parse_args()

    home = os.getcwd()

    create_dir("build")
    os.chdir("build")
    write_last(args.space[0])

    create_dir(args.space[0])
    os.chdir(args.space[0])

    if args.url:
        r = export_space(args.url[0], args.space[0])
        write_last(r)
        unzip_space(r)

    last = read_last()
    create_dir(args.space[0])
    os.chdir(args.space[0])

    if args.pdf or args.single_page:
        singlepage = True
    else:
        singlepage = False

#    print singlepage

    index = pageindex.Index('index.html')
    index.configure(fixlinks=singlepage)
    text = index.markdown(mindepth=1)
    print index.title
    g = codecs.open('index.md','w',encoding='utf-8')
    g.write(text)
    g.close()

#    print index.pagelist()

    for i in index.pagelist():
        filename = i['url']
        f = codecs.open(filename, encoding='utf-8').read()
        s = BeautifulSoup(f)

        l = i['depth']+1
        output = html.page(s,depth=l-1,singlepage=singlepage).prettify()
        output = '<h'+str(l)+' id="'+i['url']+'">'+i['name']+'</h'+str(l)+'>\n' + output

        newname = os.path.splitext(filename)[0]+'.md'
        f = codecs.open(newname,'w',encoding='utf-8')
        f.write(output)
        f.close()

        #print output

    spacename = args.space[0]+'_'+index.title.replace(' ','_')
    spacename = os.path.join(home, spacename)

    if singlepage:
        f = codecs.open('_output_.md','w',encoding='utf-8')

        if args.toc:
            f.write('<h1>Contents</h1>\n')
            f.write(index.html(mindepth=1))
            f.write(html.pagebreak())

        for i in index.pagelist():
            filename = os.path.splitext(i['url'])[0]+u'.md'
            text = codecs.open(filename,'r',encoding='utf-8').read()+u'\n'
            text = text + html.pagebreak()
            f.write(text)

        f.close()

    if args.pdf:
        import weasyprint
        src = weasyprint.HTML(filename='_output_.md')
        doc = src.render(stylesheets=[from_scriptroot("default.css")])
        doc.resolve_links()
    #    for d in doc.pages:
    #        print d.links
        doc.write_pdf(spacename+'.pdf')
