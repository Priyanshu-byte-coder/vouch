import gzip
import io
import tarfile

from app.models import RefType
from app.pipeline.ingest import normalize_arxiv_id, unpack
from app.pipeline.latex import bib_to_ref, cite_order_and_contexts, latex_to_text, parse_bbl, parse_bib

BBL = r"""
\begin{thebibliography}{10}
\bibitem[Vaswani et~al.(2017)]{vaswani2017attention}
A.~Vaswani, N.~Shazeer, and N.~Parmar.
\newblock Attention is all you need.
\newblock In \emph{Advances in Neural Information Processing Systems}, 2017.

\bibitem{cabanac2021}
G.~Cabanac, C.~Labb{\'e}, and A.~Magazinov.
\newblock {Tortured phrases}: A dubious writing style.
\newblock \emph{arXiv preprint arXiv:2107.06751}, 2021.
\end{thebibliography}
"""

BIB = r"""
@inproceedings{he2016deep,
  title={Deep Residual Learning for Image Recognition},
  author={He, Kaiming and Zhang, Xiangyu and Ren, Shaoqing and Sun, Jian},
  booktitle={Proceedings of the IEEE Conference on Computer Vision and Pattern Recognition},
  pages={770--778}, year={2016}
}
@misc{priem2022openalex,
  title={{OpenAlex}: A fully-open index}, author={Jason Priem and Heather Piwowar and others},
  year={2022}, eprint={2205.01833}, archivePrefix={arXiv}
}
"""

TEX = r"""
\section{Intro}
Transformers~\citep{vaswani2017attention} changed NLP. % a comment \cite{ignored}
Residual networks \cite{he2016deep, vaswani2017attention} are deep. Paper mills use odd wording \citet[p.~3]{cabanac2021}.
\begin{equation} x = \cite{inequation} \end{equation}
"""


def test_latex_to_text():
    assert latex_to_text(r"G.~Cabanac, C.~Labb{\'e} and \emph{Nature}") == "G. Cabanac, C. Labbé and Nature"
    assert latex_to_text(r"Gra\v{z}ulis and M\"{u}ller, {\em Science} 2--3") == "Gražulis and Müller, Science 2–3"


def test_parse_bbl():
    entries = parse_bbl(BBL)
    assert [k for k, _ in entries] == ["vaswani2017attention", "cabanac2021"]
    assert "Attention is all you need" in entries[0][1] and "Labbé" in entries[1][1]
    assert "arXiv:2107.06751" in entries[1][1]


def test_parse_bib_and_bib_to_ref():
    bib = parse_bib(BIB)
    r = bib_to_ref(0, "he2016deep", bib["he2016deep"])
    assert r.title == "Deep Residual Learning for Image Recognition" and r.year == 2016
    assert r.authors[:2] == ["He, Kaiming", "Zhang, Xiangyu"] and r.type_guess is RefType.conference
    o = bib_to_ref(1, "priem2022openalex", bib["priem2022openalex"])
    assert o.arxiv_id == "2205.01833" and o.type_guess is RefType.preprint and o.authors == ["Priem, Jason", "Piwowar, Heather"]
    assert o.title == "OpenAlex: A fully-open index"


def test_cite_order_and_contexts():
    order, ctx = cite_order_and_contexts(TEX)
    assert order == ["vaswani2017attention", "he2016deep", "cabanac2021"]  # comment and equation ignored
    assert len(ctx["vaswani2017attention"]) == 2
    assert ctx["cabanac2021"][0].startswith("Paper mills use odd wording [CITATION]")


def test_normalize_arxiv_id():
    for s in ("1706.03762", "arXiv:1706.03762", "https://arxiv.org/abs/1706.03762", "https://arxiv.org/pdf/1706.03762.pdf"):
        assert normalize_arxiv_id(s) == "1706.03762"


def test_unpack_formats():
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, text in (("main.tex", TEX), ("refs.bbl", BBL), ("fig.png", "x")):
            data = text.encode()
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    assert set(unpack(buf.getvalue())) == {"main.tex", "refs.bbl"}
    assert unpack(gzip.compress(TEX.encode()))["main.tex"].lstrip().startswith(r"\section")
    assert unpack(b"%PDF-1.5 ...") == {"__pdf__": ""}


def test_revtex_bibinfo_macros():  # E5 audit: APS bibliographies leaked "author author" / "journal journal"
    from app.pipeline.latex import latex_to_text
    s = r"\BibitemOpen \bibfield {author} {\bibinfo {author} {\bibnamefont {S.~W.}\ \bibnamefont {Hawking}},\ }\href@noop {} {\bibfield {journal} {\bibinfo {journal} {Commun. Math. Phys.}}\ }\textbf {\bibinfo {volume} {43}},\ \bibinfo {pages} {199} (\bibinfo {year} {1975})\BibitemShut {NoStop}"
    out = latex_to_text(s)
    assert "author" not in out and "journal journal" not in out and "NoStop" not in out
    assert "Hawking" in out and "Commun. Math. Phys." in out and "1975" in out
