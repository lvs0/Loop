from bs4 import BeautifulSoup

def remove_tag(root, tag, class_=None, id=None):
    if class_ == None and not id == None:
        res = root.find_all(tag, id=id)
    if not class_ == None and id == None:
        res = root.find_all(tag, class_=class_)
    if not class_ == None and not id == None:
        res = root.find_all(tag, class_=class_, id=id)
    if class_ == None and id == None:
        res = root.find_all(tag)

    for h in res:
        h.decompose()

