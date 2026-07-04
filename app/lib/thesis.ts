// Thesis metadata shown on the landing page and the PDF cover. Edit these here;
// the submission date is a deliberate placeholder until the date is fixed.
export const THESIS = {
  course: "HFWU Nürtingen-Geislingen · Master",
  author: {
    name: "Jannik Lindner",
    program: "Master Controlling",
    degree: "Master of Arts",
  },
  title:
    "Dynamic Risk Management in Corporate Treasury — Volatility-Control Strategies incorporating Digital Assets",
  examiners: [
    { role: "Erstprüfer", name: "Prof. Holger Graf" },
    { role: "Zweitprüferin", name: "Prof. Anja Blatter" },
  ],
  // Placeholder — replace with the real submission date (TT.MM.JJJJ).
  submissionDate: "TT.MM.JJJJ",
} as const;
