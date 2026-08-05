from pathlib import Path

p = Path(__file__).resolve().parent / "main.tex"
t = p.read_text(encoding="utf-8")
a = t.index(r"\begin{promptbox}[two of the sixty]")
b = t.index(r"\end{promptbox}", a) + len(r"\end{promptbox}")
new = r"""\begin{promptbox}[two of the sixty]
\textbf{field}\quad The patient is allergic to penicillin\\
\phantom{\textbf{field}}\quad SOURCE: the patient's adult son\\
\phantom{\textbf{field}}\quad CERTAINTY: reported, not confirmed against records\\[3pt]
\textbf{paren}\quad There were 18 affected accounts (per support said 18,\\
\phantom{\textbf{paren}}\quad the data team said 25; conflicting figures)
\end{promptbox}"""
p.write_text(t[:a] + new + t[b:], encoding="utf-8")
print("promptbox repaired")
