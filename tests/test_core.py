import os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import strip_core as c

WORK = (0, 0, 1920, 1040)
WIN = (-8, -8, 1928, 1048)
BOX = (786, 965, 1554, 1005)
ROW = [("a", (793, 1011, 813, 1031)), ("b", (813, 1011, 833, 1031)), ("c", (832, 1011, 852, 1031)),
       ("d", (852, 1011, 892, 1031)), ("m", (1386, 1011, 1458, 1031)), ("e", (1461, 1011, 1520, 1031)),
       ("u", (1524, 1011, 1544, 1031))]


class T(unittest.TestCase):
    def test_contrast_all_rows(self):
        for k, (bg, fg) in c.COLORS.items():
            self.assertGreaterEqual(c.contrast(bg, fg), 4.5, k)

    def test_text(self):
        self.assertEqual(c.strip_text("Code", "Model: Sonnet 5.5", "Effort: Medium"), "Code · Sonnet 5.5 Medium")
        self.assertEqual(c.strip_text("Cowork", "Model: Opus 5.5 Medium", None), "Cowork · Opus 5.5 Medium")
        self.assertEqual(c.strip_text("Cowork", "Model: Opus 5.5 Medium", "Effort: Medium"), "Cowork · Opus 5.5 Medium")
        self.assertEqual(c.strip_text("Code", None, "Effort: Medium"), "Code · model ?")
        self.assertEqual(c.strip_text("Code", "Model: ", None), "Code · model ?")

    def test_pending(self):
        self.assertEqual(c.pending_text("Cowork"), "Cowork · …")

    def test_code_pos1(self):
        rect, pos = c.place("Code", BOX, ROW, WIN, WORK)
        self.assertEqual(pos, 1)
        self.assertEqual(rect, (900, 1012, 1378, 1030))   # 8 px clearance, 18 px high, centred on 1021

    def test_cowork_always_pos2(self):
        rect, pos = c.place("Cowork", (785, 952, 1553, 1000), ROW, WIN, WORK)
        self.assertEqual((rect, pos), ((785, 932, 1553, 950), 2))

    def test_narrow_gap_falls_back(self):
        row = [("d", (852, 1011, 892, 1031)), ("m", (1000, 1011, 1072, 1031))]   # gap 108
        rect, pos = c.place("Code", BOX, row, WIN, WORK)
        self.assertEqual(pos, 2)
        self.assertEqual(rect, (786, 945, 1554, 963))

    def test_missing_anchors_falls_back(self):
        rect, pos = c.place("Code", BOX, [], WIN, WORK)
        self.assertEqual(pos, 2)

    def test_never_past_work_area(self):
        # window dragged so the row is under the taskbar: pos 1 clamps out, pos 2 is used
        box = (786, 1005, 1554, 1045); row = [(n, (r[0], r[1] + 40, r[2], r[3] + 40)) for n, r in ROW]
        rect, pos = c.place("Code", box, row, WIN, WORK)
        self.assertEqual(pos, 2)
        self.assertLessEqual(rect[3], 1040)

    def test_straddling_two_monitors(self):
        # window spans monitor A (0..1920) and B (-1920..0); strip lands on B, outside A's work area but inside B's
        zones = [((0, 0, 1920, 1080), (0, 0, 1920, 1040)), ((-1920, 0, 0, 1080), (-1920, 0, 0, 1040))]
        win = (-900, 100, 600, 900); box = (-700, 700, 400, 740)
        row = [("d", (-690, 746, -650, 766)), ("m", (200, 746, 272, 766))]
        rect, pos = c.place("Code", box, row, win, (0, 0, 1920, 1040), zones=zones)
        self.assertEqual(pos, 1)
        # a strip inside A's taskbar band is rejected even though the window's own monitor might be B
        zones2 = [((0, 0, 1920, 1080), (0, 0, 1920, 1040))]
        box2 = (700, 1000, 1500, 1040); row2 = [("d", (710, 1046, 750, 1066)), ("m", (1300, 1046, 1370, 1066))]
        r2, p2 = c.place("Code", box2, row2, (600, 100, 1600, 1075), (0, 0, 1920, 1040), zones=zones2)
        self.assertEqual(p2, 2)

    def test_no_room(self):
        self.assertIsNone(c.place("Cowork", (785, 5, 1553, 50), [], WIN, WORK))

    def test_ellipsize(self):
        m = lambda s: 7 * len(s)
        self.assertEqual(c.ellipsize("abcdef", 100, m), "abcdef")
        self.assertEqual(c.ellipsize("abcdefghijklmnopqrstuvwxyz", 70, m), "abcdefghi…")


if __name__ == "__main__":
    unittest.main()
