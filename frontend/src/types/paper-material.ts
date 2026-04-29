/**
 * ft-034 P0-6: material DTOs (sections / figures / tables / equations / citations).
 *
 * Per ft-034 P0-6 + review-D D1: ``EquationDTO`` now mirrors backend
 * ``EquationSerializer`` 1-to-1, including ``paper_arxiv_id`` / ``eq_label`` /
 * ``bbox`` (previously dropped by the inline dict).
 */

export interface SectionDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  path: string;
  level: number;
  char_offset_start: number;
  char_offset_end: number;
  raw_text: string;
}

export interface FigureDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  fig_label: string;
  page: number;
  bbox: number[] | null;
  caption: string;
  image_path: string;
}

export interface TableDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  tbl_label: string;
  page: number;
  bbox: number[] | null;
  caption: string;
  raw_text: string;
}

/**
 * ft-034 P0-6 + review-D D1: full equation DTO matching backend
 * ``EquationSerializer``. Old type was missing ``paper_arxiv_id`` / ``eq_label``
 * / ``bbox`` because PaperDetailView 之前手写 inline dict — fixed in P0-6.
 *
 * ``bbox`` 用 4-tuple ``[x0,y0,x1,y1]`` 风格描述位置，但 Python JSONField
 * 实际写的是普通 list，前端用 ``number[] | null`` 兼容（避免 nullable tuple
 * 在严格模式下不友好）。
 */
export interface EquationDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  eq_label: string | null;
  page: number;
  bbox: number[] | null;
  latex_or_text: string;
  inline_or_display: string;
}

export interface CitationDTO {
  material_id: string;
  paper_arxiv_id: string;
  seq: number;
  bibkey: string;
  raw_text: string;
  title: string;
  year: number | null;
}
