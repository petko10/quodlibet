from unittest import TestCase, makeSuite
from tests import registerCase
from songlist import PlaylistModel, PlaylistMux
import gobject, gtk

class SongWatcher(gtk.Object):
    SIG_PYOBJECT = (gobject.SIGNAL_RUN_LAST, gobject.TYPE_NONE, (object,))    
    __gsignals__ = {'song-started': SIG_PYOBJECT}

    def song_started(self, song): self.emit('song-started', song)

gobject.type_register(SongWatcher)

class Playlist(TestCase):
    def setUp(self):
        self.pl = PlaylistModel()
        self.pl.set(range(10))
        self.failUnless(self.pl.current is None)

    def test_isempty(self):
        self.failIf(self.pl.is_empty())
        self.pl.clear()
        self.failUnless(self.pl.is_empty())

    def test_get(self):
        self.assertEqual(self.pl.get(), range(10))
        self.pl.set(range(12))
        self.assertEqual(self.pl.get(), range(12))

    def test_next(self):
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 0)
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 1)
        self.pl.go_to(9)
        self.failUnlessEqual(self.pl.current, 9)
        self.pl.next()
        self.failUnless(self.pl.current is None)

    def test_contains(self):
        self.failUnless(1 in self.pl)
        self.failUnless(8 in self.pl)
        self.failIf(22 in self.pl)

    def test_removal(self):
        self.pl.go_to(8)
        for i in range(3, 8):
            self.pl.remove(self.pl.find(i))
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 9)

    def test_next_repeat(self):
        self.pl.repeat = True
        self.pl.go_to(3)
        for i in range(9): self.pl.next()
        self.assertEqual(self.pl.current, 2)
        for i in range(12): self.pl.next()
        self.assertEqual(self.pl.current, 4)

    def test_shuffle(self):
        self.pl.shuffle = 1
        for i in range(5):
            numbers = [self.pl.current for i in range(10)
                       if self.pl.next() or True]
            self.assertNotEqual(numbers, range(10))
            numbers.sort()
            self.assertEqual(numbers, range(10))
            self.pl.next()
            self.assertEqual(self.pl.current, None)

    def test_weighted_shuffle(self):
        self.pl.shuffle = 2
        r0 = {'~#rating': 0}
        r1 = {'~#rating': 1}
        r2 = {'~#rating': 2}
        r3 = {'~#rating': 3}
        self.pl.set([r0, r1, r2, r3])
        songs = [self.pl.current for i in range(1000)
                 if self.pl.next() or True]
        self.assert_(songs.count(r1) > songs.count(r0))
        self.assert_(songs.count(r2) > songs.count(r1))
        self.assert_(songs.count(r3) > songs.count(r2))

    def test_shuffle_repeat(self):
        self.pl.shuffle = 1
        self.pl.repeat = True
        numbers = [self.pl.current for i in range(30)
                   if self.pl.next() or True]
        allnums = range(10) * 3
        allnums.sort()
        self.assertNotEqual(numbers, allnums)
        numbers.sort()
        self.assertEqual(numbers, allnums)

    def test_previous(self):
        self.pl.go_to(2)
        self.failUnlessEqual(self.pl.current, 2)
        self.pl.previous()
        self.failUnlessEqual(self.pl.current, 1)
        self.pl.previous()
        self.failUnlessEqual(self.pl.current, 0)
        self.pl.previous()
        self.failUnlessEqual(self.pl.current, 0)

    def test_go_to_saves_current(self):
        self.pl.go_to(5)
        self.failUnlessEqual(self.pl.current, 5)
        self.pl.set([5, 10, 15, 20])
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 10)

    def test_go_to_shuffle(self):
        self.pl.shuffle = 1
        for i in range(5):
            self.pl.go_to(5)
            self.failUnlessEqual(self.pl.current, 5)
            self.pl.go_to(1)
            self.failUnlessEqual(self.pl.current, 1)

    def test_go_to_none(self):
        for i in range(5):
            self.pl.go_to(None)
            self.failUnlessEqual(self.pl.current, None)
            self.pl.next()
            self.failUnlessEqual(self.pl.current, 0)

    def test_reset(self):
        self.pl.go_to(5)
        self.failUnlessEqual(self.pl.current, 5)
        self.pl.reset()
        self.failUnlessEqual(self.pl.current, None)
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 0)

    def test_reset_shuffle(self):
        self.pl.shuffle = 1
        self.pl.go_to(5)
        self.failUnlessEqual(self.pl.current, 5)
        self.pl.reset()
        self.failUnlessEqual(self.pl.current, None)

    def test_restart(self):
        self.pl.go_to(1)
        self.pl.set([101, 102, 103, 104])
        self.pl.next()
        self.failUnlessEqual(self.pl.current, 101)

    def shutDown(self):
        self.pl.destroy()

registerCase(Playlist)

class Mux(TestCase):
    def setUp(self):
        self.q = PlaylistModel()
        self.pl = PlaylistModel()
        self.w = SongWatcher()
        self.mux = PlaylistMux(self.w, self.q, self.pl)
        self.failUnless(self.pl.current is None)

    def test_only_pl(self):
        self.pl.set(range(10))
        self.failUnless(self.mux.current is None)
        songs = [self.next() for i in range(10)]
        self.failUnlessEqual(songs, range(10))
        self.next()
        self.failUnless(self.mux.current is None)

    def test_only_q(self):
        self.q.set(range(10))
        self.failUnless(self.mux.current is None)
        songs = [self.next() for i in range(10)]
        self.failUnlessEqual(songs, range(10))
        self.next()
        self.failUnless(self.mux.current is None)

    def test_mixed(self):
        self.q.set(range(5))
        self.pl.set(range(5, 10))
        self.failUnless(self.mux.current is None)
        songs = [self.next() for i in range(10)]
        self.failUnlessEqual(songs, range(10))
        self.next()
        self.failUnless(self.mux.current is None)

    def test_halfway(self):
        self.pl.set(range(10))
        self.failUnless(self.mux.current is None)
        songs = [self.next() for i in range(5)]
        self.q.set(range(100, 105))
        songs.extend([self.next() for i in range(10)])
        self.failUnlessEqual(
            songs, [0, 1, 2, 3, 4, 100, 101, 102, 103, 104, 5, 6, 7, 8, 9])
        self.next()
        self.failUnless(self.mux.current is None)

    def test_removal(self):
        self.pl.set(range(0, 5))
        self.q.set(range(10, 15))
        songs = [self.next() for i in range(3)]
        self.q.remove(self.q.find(14))
        self.q.remove(self.q.find(13))
        songs.extend([self.next() for i in range(5)])
        self.failUnlessEqual(songs, [10, 11, 12, 0, 1, 2, 3, 4])

    def next(self):
        self.mux.next()
        song = self.mux.current
        self.w.song_started(self.mux.current)
        while gtk.events_pending(): gtk.main_iteration()
        return song

    def tearDown(self):
        self.w.destroy()

registerCase(Mux)
