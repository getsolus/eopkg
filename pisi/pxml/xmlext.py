# Copyright (C) 2005 - 2007, TUBITAK/UEKAE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation; either version 2 of the License, or (at your option)
# any later version.
#
# Please read the COPYING file.
#

"""
 xmlext is a helper module for accessing XML files using
 xml.dom.minidom . It is a convenient wrapper for some
 DOM functions, and provides path based get/add functions
 as in KDE API.

 function names are mixedCase for compatibility with minidom,
 an 'old library'

 this implementation uses piksemel
"""

import xml.etree.ElementTree as xml
from typing import Iterable, Iterator

from pisi import translate as _


def getAllNodes(node: xml.Element, tagPath: str) -> list[xml.Element]:
    """retrieve all nodes that match a given tag path."""
    tags = tagPath.split("/")
    if len(tags) == 0:
        return []
    nodeList = [node]  # basis case
    for tag in tags:
        nodeList = []
        for x in (getTagByName(x, tag) for x in nodeList):
            nodeList.extend(x)
        if len(nodeList) == 0:
            return []
    return nodeList


def getNodeAttribute(node: xml.Element, attrname: str) -> str | None:
    """get named attribute from DOM node"""
    return node.attrib.get(attrname)


def setNodeAttribute(node: xml.Element, attrname: str, value: str):
    """set named attribute from DOM node"""
    node.attrib[attrname] = value


def getChildElts(parent: xml.Element) -> Iterator[xml.Element]:
    """get only child elements"""
    return iter(parent)


def getTagByName(parent: xml.Element, childName: str) -> Iterator[xml.Element]:
    return parent.iterfind(childName)


def getNodeText(node: xml.Element, tagpath="") -> str | None:
    """get the first child and expect it to be text!"""
    child = getNode(node, tagpath)
    if child is None:
        return None
    return child.text


def getChildText(node_s, tagpath):
    """get the text of a child at the end of a tag path"""
    node = getNode(node_s, tagpath)
    if not node:
        return None
    return getNodeText(node)


def getNode(node: xml.Element, tagpath: str) -> xml.Element | None:
    """
    returns the *first* matching node for given tag path.
    tagpath is an XPath.
    """
    return node.find(tagpath)


def createTagPath(node: xml.Element, tags: Iterable[str]):
    """create new child at the end of a tag chain starting from node
    no matter what"""
    for tag in tags:
        node = xml.SubElement(node, tag)
    return node


def addTagPath(
    node: xml.Element, tags: Iterable[str], newnode: xml.Element | None = None
):
    """add newnode at the end of a tag chain, smart one"""
    node = createTagPath(node, tags)
    if newnode:  # node to add specified
        node.append(newnode)
    return node


def addNode(
    node: xml.Element, tagpath: str, newnode: xml.Element | None = None, branch=True
) -> xml.Element:
    """add a new node at the end of the tree and returns it
    if newnode is given adds that node, too."""

    tags = []
    if tagpath != "":
        tags = tagpath.split("/")  # tag chain
    else:
        addTagPath(node, [], newnode)
        return node  # FIXME: is this correct!?!?

    assert len(tags) > 0  # we want a chain

    # iterative code to search for the path

    if branch:
        rem = 1
    else:
        rem = 0

    while len(tags) > rem:
        tag = tags.pop(0)
        nodeList = list(getTagByName(node, tag))
        if len(nodeList) == 0:  # couldn't find
            tags.insert(0, tag)  # put it back in
            return addTagPath(node, tags, newnode)
        else:
            node = nodeList[len(nodeList) - 1]  # discard other matches
    else:
        # had only one tag..
        return addTagPath(node, tags, newnode)


def addText(node, tagpath, text):
    node = addNode(node, tagpath)
    node.insertData(text)


def newNode(node, tag: str) -> xml.Element:
    return xml.Element(tag)
