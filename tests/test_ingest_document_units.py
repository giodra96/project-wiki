from __future__ import annotations

import builtins
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from scripts import ingest_document


class ChunkingTests(unittest.TestCase):
    doc_id = "DOCIN-20260820-001"

    def test_section_boundaries_create_distinct_chunks_with_correct_metadata(self) -> None:
        blocks = [
            ingest_document.TextBlock("# Alpha", heading="Alpha", page=1, starts_section=True),
            ingest_document.TextBlock("Administrators must export reports.", heading="Alpha", page=1),
            ingest_document.TextBlock("# Beta", heading="Beta", page=2, starts_section=True),
            ingest_document.TextBlock("Customers should import data.", heading="Beta", page=2),
        ]

        chunks = ingest_document.build_chunks(self.doc_id, blocks, max_words=80)

        self.assertEqual([chunk.id for chunk in chunks], [f"{self.doc_id}-CH-001", f"{self.doc_id}-CH-002"])
        self.assertEqual([chunk.heading for chunk in chunks], ["Alpha", "Beta"])
        self.assertEqual([(chunk.page_start, chunk.page_end) for chunk in chunks], [(1, 1), (2, 2)])
        self.assertEqual(chunks[0].text, "# Alpha\n\nAdministrators must export reports.")
        self.assertEqual(chunks[1].text, "# Beta\n\nCustomers should import data.")
        self.assertIn("requirement-language", chunks[0].hints)
        self.assertIn("recommendation-language", chunks[1].hints)

    def test_line_and_paragraph_boundaries_are_preserved(self) -> None:
        blocks = [
            ingest_document.TextBlock("Line one\nLine two", heading="Alpha"),
            ingest_document.TextBlock("Paragraph two.", heading="Alpha"),
        ]

        chunks = ingest_document.build_chunks(self.doc_id, blocks, max_words=80)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].text, "Line one\nLine two\n\nParagraph two.")
        self.assertEqual(chunks[0].word_count, 6)
        self.assertEqual(chunks[0].char_count, len(chunks[0].text))

    def test_word_limit_splits_large_block_into_stable_sequential_chunks(self) -> None:
        words = [f"word-{index}" for index in range(165)]
        blocks = [ingest_document.TextBlock(" ".join(words), heading="Large Section", page=3)]

        chunks = ingest_document.build_chunks(self.doc_id, blocks, max_words=80)

        self.assertEqual([chunk.sequence for chunk in chunks], [1, 2, 3])
        self.assertEqual([chunk.word_count for chunk in chunks], [80, 80, 5])
        self.assertEqual([chunk.id for chunk in chunks], [
            f"{self.doc_id}-CH-001",
            f"{self.doc_id}-CH-002",
            f"{self.doc_id}-CH-003",
        ])
        self.assertTrue(all((chunk.page_start, chunk.page_end) == (3, 3) for chunk in chunks))
        self.assertEqual(" ".join(chunk.text for chunk in chunks), " ".join(words))


class DocumentIdTests(unittest.TestCase):
    def test_first_id_is_001_when_documents_directory_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            documents_root = Path(temporary_directory) / "missing" / "documents"
            today = ingest_document.datetime.now().strftime("%Y%m%d")

            doc_id = ingest_document.next_doc_id(documents_root)

        self.assertEqual(doc_id, f"DOCIN-{today}-001")

    def test_next_id_follows_highest_matching_id_and_ignores_other_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            documents_root = Path(temporary_directory)
            today = ingest_document.datetime.now().strftime("%Y%m%d")
            (documents_root / f"DOCIN-{today}-001").mkdir()
            (documents_root / f"DOCIN-{today}-003").mkdir()
            (documents_root / f"DOCIN-{today}-invalid").mkdir()
            (documents_root / "DOCIN-19990101-999").mkdir()

            doc_id = ingest_document.next_doc_id(documents_root)

        self.assertEqual(doc_id, f"DOCIN-{today}-004")


class IntakeIndexTests(unittest.TestCase):
    def test_readding_same_document_is_an_idempotent_noop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            index_path = root / "intake" / "INDEX.md"
            source = root / "requirements.md"
            source.write_text("Requirement", encoding="utf-8")
            doc_id = "DOCIN-20260820-001"
            ingest_document.ensure_intake_index(index_path, doc_id, "Requirements", source)
            original_content = index_path.read_text(encoding="utf-8")

            with patch.object(ingest_document, "atomic_write_text") as atomic_write:
                ingest_document.ensure_intake_index(index_path, doc_id, "Changed Title", source)

            self.assertEqual(index_path.read_text(encoding="utf-8"), original_content)
            self.assertEqual(sum(doc_id in line for line in original_content.splitlines()), 1)
            atomic_write.assert_not_called()


class MissingExtractionDependencyTests(unittest.TestCase):
    def assert_missing_dependency(self, module_name: str, extractor: object, message: str) -> None:
        original_import = builtins.__import__

        def import_without_module(name: str, *args: object, **kwargs: object) -> object:
            if name == module_name:
                raise ImportError(f"{module_name} unavailable")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=import_without_module):
            with self.assertRaisesRegex(ingest_document.MissingDependencyError, message):
                extractor(Path("unused"))

    def test_pdf_extraction_reports_missing_pymupdf(self) -> None:
        self.assert_missing_dependency("fitz", ingest_document.extract_pdf, "PDF extraction requires PyMuPDF")

    def test_docx_extraction_reports_missing_python_docx(self) -> None:
        self.assert_missing_dependency("docx", ingest_document.extract_docx, "DOCX extraction requires python-docx")


class DocxExtractionTests(unittest.TestCase):
    def test_paragraphs_and_tables_preserve_document_order(self) -> None:
        @dataclass
        class Style:
            name: str

        @dataclass
        class Paragraph:
            text: str
            style: Style

        @dataclass
        class Cell:
            text: str

        @dataclass
        class Row:
            cells: list[Cell]

        @dataclass
        class Table:
            rows: list[Row]

        class Document:
            def iter_inner_content(self) -> object:
                return iter(
                    (
                        Paragraph("Alpha", Style("Heading 1")),
                        Paragraph("Before table", Style("Normal")),
                        Table([Row([Cell("A1"), Cell("B1")]), Row([Cell("A2"), Cell("B2")])]),
                        Paragraph("After table", Style("Normal")),
                    )
                )

        class DocxModule:
            @staticmethod
            def Document(_: Path) -> Document:
                return Document()

        with patch.dict(sys.modules, {"docx": DocxModule()}):
            blocks = ingest_document.extract_docx(Path("ordered.docx"))

        self.assertEqual(
            [block.text for block in blocks],
            ["Alpha", "Before table", "A1 | B1\nA2 | B2", "After table"],
        )
        self.assertEqual([block.heading for block in blocks], ["Alpha"] * 4)
        self.assertEqual([block.starts_section for block in blocks], [True, False, True, False])


if __name__ == "__main__":
    unittest.main()