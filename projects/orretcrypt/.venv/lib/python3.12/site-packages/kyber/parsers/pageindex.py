import os, re
from bs4 import BeautifulSoup
import functions

import markdown

class Index:
    def __init__(self,indexfile):
        self.pages = []
        self.fixlinks = False

        f = open(indexfile).read()
        self.root = BeautifulSoup(f)
        self.toc = self.table_of_contents(self.root)
        self.makelist(self.toc,0)

        self.title = self.title_index(self.root)
        print self.markdown(ordered=True, mindepth=2)
        print markdown.markdown(self.markdown(ordered=True, mindepth=2))

    def table_of_contents(self, node):
        functions.remove_tag(node,'div',id='footer')
        functions.remove_tag(node,'div','pageSection','main-content')
        functions.remove_tag(node,'div','pageSectionHeader')
        functions.remove_tag(node,'div',id='main-header')
        functions.remove_tag(node,'img')
        return node.find('div','pageSection').ul

    def add(self, item):
        self.pages.append(item)

    def clear(self):
        del self.pages[:]

    def makelist(self, item, depth, char='*'):
        node = {'name': item.a.text, 'depth': depth, 'url': item.a['href']}
        self.pages.append(node)

        for x in item.li.find_all('ul',recursive=False):
            self.makelist(x, depth+1, char)

    def configure(self, fixlinks=False):
        self.fixlinks = fixlinks

    def title_index(self, node):
        output = node.find('title').text
        output = re.sub('.*\((.*)\)','\g<1>', output)
        return output.lstrip()

    def pagelist(self):
        return self.pages
            
    def markdown(self, mindepth=0, ordered=False):
        output = ""
        if ordered:
            char = '1.'
        else:
            char = '*'

        if self.fixlinks:
            h = '#'
        else:
            h = ''

        for i in self.pages:
            if i['depth'] >= mindepth:

                output += ' '*(i['depth']-mindepth)*4 + char + ' '
                if self.fixlinks:
                    filename = i['url']
                else:
                    filename = os.path.splitext(i['url'])[0]+'.md'
                output += self.link(i['name'], h+filename)
                output += '\n'

        return output

    def html(self, mindepth=0, ordered=False):
        return markdown.markdown(self.markdown(ordered=ordered, mindepth=mindepth))

    def link(self, name, url):
        output = ""
        output += '['+name+']'
        output += '('+url+')'
        return output
