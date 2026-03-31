import os, re
from bs4 import BeautifulSoup

import pageindex 
import functions

def image(tag):
    src = tag.attrs['src']
    if 'width' in tag.attrs:
        tag.attrs = {'width':tag.attrs['width']}
    else:
        tag.attrs = {}

    tag.attrs['src'] = src

def fix_anchors(node):
    for a in node.find_all('a'):
        if 'href' in a:
            if os.path.isfile(a['href']):
                a['href'] = '#'+a['href']

def fix_links(node):
    for a in node.find_all('a'):
        if os.path.isfile(a['href']):
            a['href'] = os.path.splitext(a['href'])[0]+'.md'


def header(tag, depth, mindepth):
    tag.attrs = {}
    depth = depth - mindepth + int(re.sub('h([1-6])','\g<1>',tag.name))
    depth += 1
    tag.name = 'h'+str(depth)

def pagebreak():
    return '<p style="page-break-after:always !important;"></p>'

def gliffy_diagram(tag):
    pass

def page(node, depth=0, mindepth=0, singlepage=False):
    functions.remove_tag(node,'div',id='footer')
    functions.remove_tag(node,'head')
    node = node.find('div','wiki-content group',id='main-content')

    [x.unwrap() for x in node.find_all('span','confluence-embedded-file-wrapper')]

    [image(x) for x in node.find_all('img')]

    [header(x, depth, mindepth) for x in node.find_all(['h1','h2','h3','h4','h5','h6'])]

    if singlepage:
        fix_anchors(node)
    else:
        fix_links(node)

    return node


