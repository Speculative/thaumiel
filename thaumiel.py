# A lightweight SCP Wiki browser for your terminal

# Article fetching and parsing
from bs4 import BeautifulSoup
import urllib.request
import urllib.parse

# Cache
import sqlite3

# For pretty printing
import shutil
import textwrap

# CLI
import argparse

BASE_URL = 'http://www.scp-wiki.net'
SERIES = ['http://www.scp-wiki.net/scp-series',
          'http://www.scp-wiki.net/scp-series-2',
          'http://www.scp-wiki.net/scp-series-3']
CACHE = True
PROMPT = "bright@site-01> "


class SCPDatabase:
    def __init__(self):
        self.index = None
        self.cache = None

        if CACHE:
            self.cache = LocalCache("scp.db")

        self.populate_index()

    def populate_index(self):
        if CACHE:
            if self.cache.has_index():
                self.index = SCPIndexFactory.from_cache(self.cache)
            else:
                self.index = SCPIndexFactory.from_web(SERIES)
                self.cache.cache_index(self.index)
        else:
            print("Populating cache from series...")
            self.index = SCPIndexFactory.from_web(SERIES)

    def get_index(self):
        return self.index

    def get_article(self, designation):
        index_entry = self.index.find(designation)
        if index_entry:
            return SCPArticleFactory.from_web(index_entry.get_url())
        else:
            # Article not in the index
            print("Entry doesn't exist!")
            return None
        # if CACHE:
        #    if self.cache.has_entry(designation):
        #        return self.cache.load_entry()
        #    else:
        #        article =
        #        self.cache.cache_article(article)
        # else:


class SCPIndex:
    def __init__(self):
        # Map {"designation": SCPIndexEntry}
        self.index = {}
        self.ordering = []

    def extend(self, index):
        # Expects index to be [SCPIndexEntry]
        keys = [entry.get_designation() for entry in index]
        self.index.update(dict(zip(keys, index)))
        self.ordering.extend(keys)

    def find(self, designation):
        if designation in self.index:
            return self.index[designation]
        else:
            return None

    def __iter__(self):
        for entry in self.ordering:
            yield self.index[entry]


class SCPIndexFactory:
    def from_web(series):
        # Expects [string] of series urls
        index = SCPIndex()
        i = 1
        for s in series:
            with urllib.request.urlopen(s) as response:
                html = response.read()
                series_parser = SCPSeriesDOM(html)
                index.extend(series_parser.get_entries())
            print("series {} complete".format(i))
            i += 1
        return index

    def from_cache(cache):
        return cache.load_index()


class SCPSeriesDOM:
    def __init__(self, dom):
        self.dom = BeautifulSoup(dom, "html.parser")

    def get_entries(self):
        entries = []
        # Magic
        entry_list = self.dom.select("#page-content div.series")[0]
        list_entries = entry_list.select("li")
        for entry in list_entries:
            anchor = entry.select("a")[0]
            slug = anchor["href"]
            if slug.startswith("/scp-"):
                url = urllib.parse.urljoin(BASE_URL, slug)
                designation = anchor.getText()
                # SCP-2557
                if len(entry.contents) < 2:
                    entry = entry.contents[0]
                # Shave off the "- " at the beginning of the name
                name = entry.contents[1].lstrip(" -,")
                entries.append(SCPIndexEntry(designation, name, url))
        return entries


class SCPIndexEntry:
    def __init__(self, designation, name, url):
        self.designation = designation
        self.name = name
        self.url = url

    def __str__(self):
        s = "designation: {}\n        url: {}\n       name: {}\n"
        return s.format(self.designation, self.url, self.name)

    def get_designation(self):
        return self.designation

    def get_name(self):
        return self.name

    def get_url(self):
        return self.url


class SCPArticleFactory:
    def from_web(url):
        with urllib.request.urlopen(url) as response:
            if response.status != 200:
                print("Unable to fetch {}".format(url))
                return None
            html = response.read()
            article_parser = SCPArticleDOM(html)
            article = SCPArticle(article_parser.get_sections())
            return article

    def from_cache(cache, designation):
        pass


class SCPArticleDOM:
    def __init__(self, dom):
        self.dom = BeautifulSoup(dom, "html.parser")
        self.section_headers = []
        self.sections = {}
        self.sectioned_tree_walk()

    def sectioned_tree_walk(self):
        heading = None
        for child in self.dom.select("#page-content p"):
            if child.strong:
                heading = child.strong.getText().rstrip(": ")
                self.section_headers.append(heading)

            if heading:
                if heading not in self.sections:
                    self.sections[heading] = ""
                next_paragraph = "{}\n".format(child.getText())
                self.sections[heading] += next_paragraph

    def get_sections(self):
        return self.sections


class SCPArticle:
    def __init__(self, sections):
        self.sections = sections

    def get_sections(self):
        # TODO: NEEDS TO BE ORDERED
        return self.sections.keys()

    def get_section(self, section):
        if section in self.sections:
            return self.sections[section]
        else:
            return None


class LocalCache:
    def __init__(self, path):
        self.path = path
        self._has_index = False
        self.conn = sqlite3.connect(self.path)

        self.setup_db()

        # Check for index
        c = self.conn.cursor()
        c.execute('''SELECT COUNT(*) FROM scp_index;''')
        if c.fetchone()[0] != 0:
            self._has_index = True

    def __del__(self):
        self.conn.commit()
        self.conn.close()

    def setup_db(self):
        c = self.conn.cursor()

        c.execute('''CREATE TABLE if not exists scp_series
            (series         INT     PRIMARY KEY NOT NULL,
             url            TEXT    NOT NULL);''')

        c.execute('''CREATE TABLE if not exists scp_index
            (designation    TEXT    PRIMARY KEY NOT NULL,
             name           TEXT    NOT NULL,
             url            TEXT    NOT NULL);''')

        self.conn.commit()

    def cache_index(self, index):
        c = self.conn.cursor()
        for entry in index:
            v = (entry.get_designation(), entry.get_name(), entry.get_url())
            c.execute('''INSERT INTO scp_index VALUES (?,?,?)''', v)

    def cache_entry(self, index):
        pass

    def load_index(self):
        index = SCPIndex()
        c = self.conn.cursor()

        for row in c.execute('''SELECT * FROM scp_index;'''):
            index.extend([SCPIndexEntry(row[0], row[1], row[2])])

        return index

    def load_entry(self):
        pass

    def has_index(self):
        return self._has_index

    def has_entry(self, designation):
        pass


def pretty_print(s, indent="    "):
    width = shutils.get_terminal_size().columns
    wrapped = textwrap.wrap(s,
                            width,
                            initial_indent=indent,
                            subsequent_indent=indent)
    for line in wrapped:
        print(line)


def print_file(filename):
    with open(filename) as f:
        for line in f:
            print(line.strip())


def interactive_usage():
    print("SCP-[xxx] -- print SCP entry xxx\n"
          "index -- print all SCP entries\n"
          "quit/exit -- quit")


def print_index(index):
    for entry in index:
        print("{} -- {}".format(entry.get_designation(), entry.get_name()))


def dispatch_from_args(db, args):
    if args.list:
        print_index(db.get_index())
    elif args.article:
        # TODO: more specific than just printing
        article = db.get_article(args.article)
        print("==== ARTICLE SECTIONS ====")
        print(article.get_sections())
        print("==== ITEM NUMBER ====")
        print(article.get_section("Item Number"))
        print("==== OBJECT CLASS ====")
        print(article.get_section("Object Class"))
        print("==== CONTAINMENT PROCEDURES ====")
        print(article.get_section("Special Containment Procedures"))
        print("==== DESCRIPTION ====")
        print(article.get_section("Description"))


def interactive(db):
    print_file("motd")

    line = input(PROMPT)
    while line and line != "quit" and line != "exit":
        if line == "index":
            print_index(db.get_index())
        elif line == "help":
            interactive_usage()
        else:
            db.get_article(line.strip())
        line = input(PROMPT)


if __name__ == "__main__":
    db = SCPDatabase()

    parser = argparse.ArgumentParser(description="SCP Wiki for your terminal")
    parser.add_argument("--list", "-l",
                        action="store_true",
                        help="Print SCP Article index")
    parser.add_argument("--article", "-a",
                        help="Print SCP Article",
                        type=str)

    args = parser.parse_args()
    if args:
        dispatch_from_args(db, args)
    else:
        interactive(db)
