# Copyright 2004 Joe Wreschnig, Michael Urman
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation
#
# $Id$

import os, stat
import cPickle as Pickle
import util; from util import escape
import fcntl
import time

def MusicFile(filename):
    for ext in supported.keys():
        if filename.lower().endswith(ext):
            try:
                return supported[ext](filename)
            except:
                print "W: Error loading %s" % filename
                return None
    else: return None

global library
library = None

class Unknown(str): pass

class AudioFile(dict):
    def __cmp__(self, other):
        if not hasattr(other, "get"):
            raise ValueError("songs can only be compared to other songs.")
        return (cmp(self.get("album"), other.get("album")) or
                cmp(self.get("=d"), other.get("=d")) or
                cmp(self.get("=#"), other.get("=#")) or
                cmp(self.get("artist"), other.get("artist")) or
                cmp(self.get("title"), other.get("title")))

    # True if our key's value is actually unknown, rather than just the
    # string "Unknown".
    def unknown(self, key):
        return isinstance(self.get(key), Unknown)

    def realkeys(self):
        return filter(lambda s: s and s[0] != "=" and not self.unknown(s),
                      self.keys())

    def comma(self, key):
        return self.get(key, "").replace("\n", ", ")

    def exists(self):
        return os.path.exists(self.get("=filename"))

    def valid(self):
        return (self.exists() and
                self.get("=mtime") == int(
            os.stat(self['=filename'])[stat.ST_MTIME]))
    
    # Sanity-check all sorts of things...
    def sanitize(self, filename = None):
        # File in our filename, either from what we were given or
        # our old tag name... FIXME: Remove migration after 0.4 or so.
        if filename: self["=filename"] = filename
        elif "filename" in self: self["=filename"] = self["filename"]
        elif "=filename" not in self: raise ValueError("Unknown filename!")

        # Fill in necessary values.
        self.setdefault("=lastplayed", 0)
        self.setdefault("=playcount", 0)
        for i in ["title", "artist", "album"]:
            self.setdefault(i, Unknown("Unknown"))

        # Derive disc and track numbers.
        try: self["=#"] = int(self["tracknumber"].split("/")[0])
        except (ValueError, KeyError): pass
        try: self["=d"] = int(self["discnumber"].split("/")[0])
        except (ValueError, KeyError): pass

        # Clean up Vorbis garbage.
        try: del(self["vendor"])
        except KeyError: pass

        # Remove our old filename key.
        if self.get("filename") == self["=filename"]: del(self["filename"])

        # Fill in the remaining file stuff.
        try: self["=mtime"] = int(os.stat(self['=filename'])[stat.ST_MTIME])
        except OSError: self["=mtime"] = 0
        self["=basename"] = os.path.basename(self['=filename'])
        self["=dirname"] = os.path.dirname(self['=filename'])

    def to_markup(self):
        title = self.comma("title")
        text = u'<span weight="bold" size="x-large">%s</span>' % escape(title)
        if "version" in self:
            text += u"\n<small><b>%s</b></small>" % escape(
                self.comma("version"))
        text += u"\nby %s" % escape(self.comma("artist"))

        if "performer" in self:
            text += ("\n<small>Performed by %s</small>" %
                     self.comma("performer"))

        others = ""
        if "arranger" in self:
            others += ("\narranged by " + self.comma("arranger"))
        if "lyricist" in self:
            others += ("\nlyrics by " + self.comma("lyricist"))
        if "conductor" in self:
            others += ("\nconducted by " + self.comma("conductor"))
        if "author" in self:
            others += ("\nwritten by " + self.comma("author"))

        if others:
            others = others.strip().replace("\n", "; ")
            others = others[0].upper() + others[1:]
            text += "\n<small>%s</small>" % escape(others.strip())

        if not self.unknown("album"):
            album = u"\n<b>%s</b>" % escape(self.comma("album"))
            if "discnumber" in self:
                album += u" - Disc " + escape(self.comma("discnumber"))
            if "part" in self:
                album += u" - <b>%s</b>" % escape(self.comma("part"))
            if "tracknumber" in self:
                album += u" - Track " + escape(self.comma("tracknumber"))
            text += album
        return text

    def get_played(self):
        count = self["=playcount"]    
        if count == 0: return "Never"
        else:
            t = time.localtime(self["=lastplayed"])
            tstr = time.strftime("%F, %X", t)
            return "%d times, recently on %s" % (count, tstr)

    def to_dump(self):
        s = ""
        for k, v in self.items():
            if k[0] == "=": continue
            for v2 in v.split("\n"):
                s += "%s=%s\n" % (k, util.encode(v2))
        return s

    def change(self, key, old_value, new_value):
        try:
            parts = self[key].split("\n")
            try: parts[parts.index(old_value)] = new_value
            except ValueError:
                self[key] = new_value
            else:
                self[key] = "\n".join(parts)
        except KeyError: self[key] = new_value
        self.sanitize()

    def add(self, key, value):
        if key not in self: self[key] = value
        elif self.unknown(key): self[key] = value
        else: self[key] += "\n" + value
        self.sanitize()

    def remove(self, key, value):
        if self[key] == value: del(self[key])
        else:
            try:
                parts = self[key].split("\n")
                parts.remove(value)
                self[key] = "\n".join(parts)
            except ValueError:
                if key in self: del(self[key])
        self.sanitize()

    def find_cover(self):
        base = os.path.split(self['=filename'])[0]
        fns = os.listdir(base)
        images = []
        fns.sort()
        for fn in fns:
            lfn = fn.lower()
            if lfn[-4:] in ["jpeg", ".jpg", ".png", ".gif"]:
               matches = filter(lambda s: s in lfn,
                                ["front", "cover", "jacket"])
               score = len(matches)
               if score: images.append((score, os.path.join(base, fn)))
        if images: return max(images)[1]
        else: return None

class MP3File(AudioFile):

    # http://www.unixgods.org/~tilo/ID3/docs/ID3_comparison.html
    # http://www.id3.org/id3v2.4.0-frames.txt
    IDS = { "TIT1": "genre",
            "TIT2": "title",
            "TIT3": "version",
            "TPE1": "artist",
            "TPE2": "performer",
            "TPE3": "conductor",
            "TPE4": "arranger",
            "TEXT": "lyricist",
            "TLAN": "language",
            "TALB": "album",
            "TRCK": "tracknumber",
            "TPOS": "discnumber",
            "TSST": "part",
            "TSRC": "isrc",
            "TDRA": "date",
            "TDRC": "date",
            "TDOR": "date",
            "TORY": "date",
            "TCOP": "copyright",
            "TPUB": "organization",
            "USER": "license",
            }

    INVERT_IDS = { "genre": "TIT1",
                   "title": "TIT2",
                   "version": "TIT3",
                   "artist": "TPE1",
                   "performer": "TPE2",
                   "conductor": "TPE3",
                   "arranger": "TPE4",
                   "lyricist": "TEXT",
                   "language": "TLAN",
                   "isrc": "TSRC",
                   "tracknumber": "TRCK",
                   "discnumber": "TPOS",
                   "organization": "TPUB",
                   "album": "TALB",
                   "copyright": "TCOP",
                   "license": "USER"
                   }
            
    def __init__(self, filename):
        import pyid3lib
        if not os.path.exists(filename):
            raise ValueError("Unable to read filename: " + filename)
        tag = pyid3lib.tag(filename)

        for frame in tag:
            names = self.IDS.get(frame["frameid"], [])
            if not isinstance(names, list): names = [names]
            for name in map(str.lower, names):
                try:
                    text = frame["text"]
                    for codec in ["utf-8", "shift-jis", "big5", "iso-8859-1"]:
                        try: text = text.decode(codec)
                        except (UnicodeError, LookupError): pass
                        else: break
                    else: continue
                    if name in self:
                        if text in self[name]: pass
                        elif self[name] in text: self[name] = text
                        else: self[name] += "\n" + text
                    else: self[name] = text
                    self[name] = self[name].strip()
                except: pass
        self.sanitize(filename)

    def write(self):
        import pyid3lib
        tag = pyid3lib.tag(self['=filename'])
        for key, id3name in self.INVERT_IDS.items():
            try:
                while True: tag.remove(id3name)
            except ValueError: pass
            if key in self:
                if self.unknown(key): continue
                for value in self[key].split("\n"):
                    try: value = value.encode("iso-8859-1")
                    except UnicodeError: value = value.encode("utf-8")
                    tag.append({'frameid': id3name, 'text': value })
        tag.update()
        self["=mtime"] = int(os.stat(self['=filename'])[stat.ST_MTIME])

    def can_change(self, k=None):
        if k is None: return self.INVERT_IDS.keys()
        else: return k in self.INVERT_IDS.keys()

class OggFile(AudioFile):
    def __init__(self, filename):
        import ogg.vorbis
        if not os.path.exists(filename):
            raise ValueError("Unable to read filename: " + filename)
        f = ogg.vorbis.VorbisFile(filename)
        for k, v in f.comment().as_dict().iteritems():
            if not isinstance(v, list): v = [v]
            v = u"\n".join(map(unicode, v))
            self[k.lower()] = v
        self.sanitize(filename)

    def write(self):
        import ogg.vorbis
        f = ogg.vorbis.VorbisFile(self['=filename'])
        comments = f.comment()
        comments.clear()
        for key in self.realkeys():
            value = self[key]
            if not isinstance(value, list): value = value.split("\n")
            for line in value: comments[key] = line
        comments.write_to(self['=filename'])
        self["=mtime"] = int(os.stat(self['=filename'])[stat.ST_MTIME])

    def can_change(self, k = None):
        if k is None: return True
        else: return (k and k not in ["vendor"] and not k.startswith("="))

class FLACFile(AudioFile):
    def __init__(self, filename):
        import flac.metadata
        if not os.path.exists(filename):
            raise ValueError("Unable to read filename: " + filename)
        chain = flac.metadata.Chain()
        chain.read(filename)
        it = flac.metadata.Iterator()
        it.init(chain)
        vc = None
        while True:
            if it.get_block_type() == flac.metadata.VORBIS_COMMENT:
                block = it.get_block()
                vc = flac.metadata.VorbisComment(block)
                break
            if not it.next(): break

        if vc:
            for k in vc.comments:
                parts = k.split("=")
                key = parts[0].lower()
                val = util.decode("=".join(parts[1:]))
                if key in self: self[key] += "\n" + val
                else: self[key] = val
        self.sanitize(filename)

    def write(self):
        import flac.metadata
        chain = flac.metadata.Chain()
        chain.read(self['=filename'])
        it = flac.metadata.Iterator()
        it.init(chain)
        vc = None
        while True:
            if it.get_block_type() == flac.metadata.VORBIS_COMMENT:
                block = it.get_block()
                vc = flac.metadata.VorbisComment(block)
                break
            if not it.next(): break

        if vc:
            keys = [k.split("=")[0] for k in vc.comments]
            for k in keys: del(vc.comments[k])
            for key in self.realkeys():
                if self.unknown(key): continue
                value = self[key]
                if not isinstance(value, list): value = value.split("\n")
                for line in value:
                    vc.comments[key] = util.encode(line)
            chain.write(True, True)
            print "After all"
            for k in vc.comments: print k

    def can_change(self, k = None):
        if k is None: return True
        else: return (k and k not in ["vendor"] and not k.startswith("="))

class AudioFileGroup(dict):

    class Comment(unicode):
        complete = True
        def __repr__(self):
            return '%s %s' % (str(self), self.paren())

        def __str__(self):
            return util.escape(self)

        def paren(self):
            if self.shared and self.complete:
                return '(shared across all %d songs)' % self.total
            elif self.shared:
                return '(missing from %d songs)' % self.missing
            elif self.complete:
                return '(different across %d songs)' % self.total
            else:
                return '(different across %d songs, missing from %d songs)' % (
                        self.have, self.missing)

        def safenicestr(self):
            if self.shared and self.complete: return str(self)
            elif self.shared: return '%s <i>%s</i>' % (str(self), self.paren())
            else: return '<i>%s</i>' % self.paren()

    class SharedComment(Comment): shared = True
    class UnsharedComment(Comment): shared = False
    class PartialSharedComment(SharedComment): complete = False
    class PartialUnsharedComment(UnsharedComment): complete = False

    def __init__(self, songs):
        self.songcount = total = len(songs)
        keys = {}
        first = {}
        all = {}
        self.types = {}

        # collect types of songs; comment names, values, and sharedness
        for song in songs:
            self.types[repr(song.__class__)] = song # for group can_change
            for comment, val in song.iteritems():
                keys[comment] = keys.get(comment, 0) + 1
                first.setdefault(comment, val)
                all[comment] = all.get(comment, True) and first[comment] == val

        # collect comment representations
        for comment, count in keys.iteritems():
            if count < total:
                if all[comment]:
                    value = self.PartialSharedComment(first[comment])
                else:
                    value = self.PartialUnsharedComment(first[comment])
            else:
                if all[comment]:
                    value = self.SharedComment(first[comment])
                else:
                    value = self.UnsharedComment(first[comment])
            value.have = count
            value.total = total
            value.missing = total - count

            self[comment] = value

    def can_change(self, k=None):
        if k is None:
            can = True
            for song in self.types.itervalues():
                cantoo = song.can_change()
                if can is True: can = cantoo
                elif cantoo is True: pass
                else: can = dict.fromkeys(can+cantoo).keys()
        else:
            can = min([song.can_change(k) for song in self.types.itervalues()])
        return can

class Library(dict):
    def __init__(self, initial = {}):
        dict.__init__(self, initial)

    def remove(self, song):
        del(self[song['=filename']])

    def save(self, fn):
        util.mkdir(os.path.dirname(fn))
        f = file(fn, "w")
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        songs = filter(lambda s: s.exists(), self.values())
        Pickle.dump(songs, f, 2)
        f.close()

    def load(self, fn):
        # Load the database and read it in.
        try:
            if os.path.exists(fn):
                f = file(fn, "rb")
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try: songs = Pickle.load(f)
                except:
                    print "W: %s is not a QL song database." % fn
                    songs = []
                f.close()
            else: return 0, 0
        except: return 0, 0

        # Prune old entries.
        removed, changed = 0, 0
        for song in songs:
            if type(song) not in supported.values(): continue
            if song.valid():
                song.sanitize()
                fn = song.get('=filename')
                self[fn] = song
            else:
                fn = song.get('=filename', song.get("filename", ""))
                if os.path.exists(fn):
                    changed += 1
                    self[fn] = MusicFile(fn)
                    self[fn].sanitize()
                else:
                    removed += 1
        return changed, removed

    def scan(self, dirs):
        added, changed = 0, 0
        for d in dirs:
            print "Checking", d
            d = os.path.expanduser(d)
            for path, dnames, fnames in os.walk(d):
                for fn in fnames:
                    m_fn = os.path.join(path, fn)
                    if m_fn in self:
                        if self[m_fn].valid(): continue
                        else:
                            changed += 1
                            added -= 1
                    m = MusicFile(m_fn)
                    if m:
                        added += 1
                        self[m_fn] = m
                yield added, changed

supported = {}

def init(cache_fn = None):
    if util.check_ogg():
        print "Enabling Ogg Vorbis support."
        supported[".ogg"] = OggFile
    else:
        print "W: Ogg Vorbis support is disabled! Ogg files cannot be loaded."

    if util.check_mp3():
        print "Enabling MP3 support."
        supported[".mp3"] = MP3File
    else:
        print "W: MP3 support is disabled! MP3 files cannot be loaded."

    if util.check_flac():
        print "Enabling FLAC support."
        supported[".flac"] = FLACFile

    global library
    library = Library()
    if cache_fn: library.load(cache_fn)
