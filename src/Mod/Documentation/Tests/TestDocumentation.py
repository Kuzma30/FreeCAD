# SPDX-License-Identifier: LGPL-2.1-or-later
"""Unit tests for the Documentation workbench.

Only the pure helpers are covered here: format detection, size formatting
and the RTF unwrapper.  They carry the logic that is easy to get subtly
wrong and need no GUI or document to exercise.
"""

import unittest

from DocumentationObjects import (
    VIEWER_EXTERNAL,
    VIEWER_PDF,
    VIEWER_PLAINTEXT,
    VIEWER_RICHTEXT,
    human_size,
    viewer_for,
)
from DocumentationRaster import parsePages
from DocumentationViewers import rtf_to_text


class ViewerSelectionCases(unittest.TestCase):
    def testKnownFormats(self):
        self.assertEqual(viewer_for("datasheet.pdf"), VIEWER_PDF)
        self.assertEqual(viewer_for("notes.rtf"), VIEWER_RICHTEXT)
        self.assertEqual(viewer_for("page.html"), VIEWER_RICHTEXT)
        self.assertEqual(viewer_for("page.htm"), VIEWER_RICHTEXT)
        self.assertEqual(viewer_for("readme.md"), VIEWER_PLAINTEXT)
        self.assertEqual(viewer_for("log.txt"), VIEWER_PLAINTEXT)

    def testExtensionIsCaseInsensitive(self):
        self.assertEqual(viewer_for("DATASHEET.PDF"), VIEWER_PDF)
        self.assertEqual(viewer_for("Notes.RtF"), VIEWER_RICHTEXT)

    def testUnhandledFormatsGoToTheDesktop(self):
        for name in ("spec.docx", "sheet.odt", "archive.zip"):
            self.assertEqual(viewer_for(name), VIEWER_EXTERNAL)

    def testMissingOrOddNames(self):
        for name in ("noextension", "", None, ".pdf.bak"):
            self.assertEqual(viewer_for(name), VIEWER_EXTERNAL)

    def testDotsInDirectoryDoNotConfuseDetection(self):
        self.assertEqual(viewer_for("/home/a.b/c.pdf"), VIEWER_PDF)


class HumanSizeCases(unittest.TestCase):
    def testUnits(self):
        self.assertEqual(human_size(0), "0 B")
        self.assertEqual(human_size(512), "512 B")
        self.assertEqual(human_size(2048), "2.0 KB")
        self.assertEqual(human_size(5 * 1024**2), "5.0 MB")
        self.assertEqual(human_size(3 * 1024**3), "3.0 GB")

    def testUnknownSize(self):
        self.assertEqual(human_size(None), "")


class RtfToTextCases(unittest.TestCase):
    SAMPLE = (
        r"{\rtf1\ansi\ansicpg1251\deff0"
        r"{\fonttbl{\f0\fnil Times New Roman;}}"
        r"{\colortbl ;\red0\green0\blue0;}"
        r"{\info{\author Someone}{\title Spec}}"
        r"\pard\f0\fs24 Technical specification\par"
        r"Part: \b SN65DSI83\b0\par"
        r"Supply: 1.8 V \'b1 5\%\par"
        r"\tab Indented\par"
        r"Braces \{x\} and \\slash\par"
        r"}"
    )

    def testBodyTextSurvives(self):
        text = rtf_to_text(self.SAMPLE)
        self.assertIn("Technical specification", text)
        self.assertIn("SN65DSI83", text)

    def testControlGroupsAreDropped(self):
        text = rtf_to_text(self.SAMPLE)
        for unwanted in ("Times New Roman", "red0", "Someone"):
            self.assertNotIn(unwanted, text)

    def testControlWordsAreNotLeftBehind(self):
        text = rtf_to_text(self.SAMPLE)
        for unwanted in (r"\par", r"\fs24", r"\pard"):
            self.assertNotIn(unwanted, text)

    def testEscapesAreUnwrapped(self):
        text = rtf_to_text(self.SAMPLE)
        self.assertIn("{x}", text)
        self.assertIn("\\slash", text)

    def testHexEscapeDecodesToCp1251(self):
        # \'b1 is the plus-minus sign in cp1251
        self.assertIn("\u00b1", rtf_to_text(self.SAMPLE))

    def testParagraphsAndTabs(self):
        text = rtf_to_text(self.SAMPLE)
        self.assertIn("\tIndented", text)
        self.assertIn("\n", text)

    def testEmptyInput(self):
        self.assertEqual(rtf_to_text(""), "")


class PageRangeCases(unittest.TestCase):
    def testSinglePages(self):
        self.assertEqual(parsePages("1", 10), [0])
        self.assertEqual(parsePages("1,3,5", 10), [0, 2, 4])

    def testRanges(self):
        self.assertEqual(parsePages("2-5", 10), [1, 2, 3, 4])
        self.assertEqual(parsePages("1,3-5", 10), [0, 2, 3, 4])

    def testResultIsSortedAndDeduplicated(self):
        self.assertEqual(parsePages("5,1,3,1", 10), [0, 2, 4])
        self.assertEqual(parsePages("2-4,3-5", 10), [1, 2, 3, 4])

    def testWhitespaceIsTolerated(self):
        self.assertEqual(parsePages(" 1 , 3 - 4 ", 10), [0, 2, 3])

    def testOutOfRangeIsRejected(self):
        self.assertEqual(parsePages("0", 10), [])
        self.assertEqual(parsePages("11", 10), [])
        self.assertEqual(parsePages("5-20", 10), [])

    def testMalformedInputIsRejected(self):
        for text in ("abc", "1-", "-3", "1,,x", "3-1"):
            self.assertEqual(parsePages(text, 10), [], text)

    def testEmptyInput(self):
        self.assertEqual(parsePages("", 10), [])
