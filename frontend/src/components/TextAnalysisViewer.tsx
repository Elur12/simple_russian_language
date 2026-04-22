import { useEffect, useRef, useState } from "react";
import type { AnalysisResponse, ParagraphFinding, ViolationDetail } from "../api/client";

type Segment =
  | { kind: "text"; text: string }
  | { kind: "violation"; text: string; violationIndex: number; severity: string };

function splitByViolations(
  text: string,
  violations: ViolationDetail[],
  appliedViolations: Set<string>,
  skippedViolations: Set<string>,
  unitIndex: number
): Segment[] {
  type Pos = { start: number; end: number; violationIndex: number };

  const positions: Pos[] = [];
  for (let i = 0; i < violations.length; i++) {
    const id = `${unitIndex}-${i}`;
    if (appliedViolations.has(id) || skippedViolations.has(id)) continue;
    const prob = violations[i].problematic_text.trim();
    if (!prob) continue;
    const start = text.indexOf(prob);
    if (start === -1) continue;
    positions.push({ start, end: start + prob.length, violationIndex: i });
  }

  positions.sort((a, b) => a.start - b.start);

  const noOverlap: Pos[] = [];
  let lastEnd = 0;
  for (const pos of positions) {
    if (pos.start >= lastEnd) {
      noOverlap.push(pos);
      lastEnd = pos.end;
    }
  }

  const segments: Segment[] = [];
  let cursor = 0;
  for (const pos of noOverlap) {
    if (pos.start > cursor) {
      segments.push({ kind: "text", text: text.slice(cursor, pos.start) });
    }
    segments.push({
      kind: "violation",
      text: text.slice(pos.start, pos.end),
      violationIndex: pos.violationIndex,
      severity: violations[pos.violationIndex].severity,
    });
    cursor = pos.end;
  }
  if (cursor < text.length) {
    segments.push({ kind: "text", text: text.slice(cursor) });
  }

  return segments;
}

export function TextAnalysisViewer({
  analysisResult,
  sourceTitle,
  sourceUrl,
}: {
  analysisResult: AnalysisResponse;
  originalText: string;
  sourceTitle?: string | null;
  sourceUrl?: string | null;
}) {
  const [paragraphTexts, setParagraphTexts] = useState<Record<number, string>>({});
  const [appliedViolations, setAppliedViolations] = useState<Set<string>>(new Set());
  const [skippedViolations, setSkippedViolations] = useState<Set<string>>(new Set());
  // User-edited replacement text per violation (keyed by "${unit}-${violation}")
  const [editedReplacements, setEditedReplacements] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [popupPos, setPopupPos] = useState<{ top: number; left: number } | null>(null);

  const contentRef = useRef<HTMLDivElement>(null);
  const spanRefs = useRef<Record<string, HTMLSpanElement | null>>({});

  const itemByUnitIndex = new Map<number, ParagraphFinding>(
    analysisResult.items.map((item) => [item.unit_index, item])
  );

  function getCurrentText(item: ParagraphFinding): string {
    return paragraphTexts[item.unit_index] ?? item.source_text;
  }

  function getReplacementValue(id: string, fallback: string): string {
    return editedReplacements[id] ?? fallback;
  }

  useEffect(() => {
    if (selectedId === null) return;
    function handleOutsideClick(e: MouseEvent) {
      if (contentRef.current && !contentRef.current.contains(e.target as Node)) {
        setSelectedId(null);
      }
    }
    document.addEventListener("click", handleOutsideClick);
    return () => document.removeEventListener("click", handleOutsideClick);
  }, [selectedId]);

  function openPopup(id: string, spanEl: HTMLSpanElement) {
    if (selectedId === id) {
      setSelectedId(null);
      return;
    }
    spanRefs.current[id] = spanEl;
    setSelectedId(id);

    const rect = spanEl.getBoundingClientRect();
    const container = contentRef.current;
    if (container) {
      const containerRect = container.getBoundingClientRect();
      setPopupPos({
        top: rect.bottom - containerRect.top + container.scrollTop + 8,
        left: Math.max(0, rect.left - containerRect.left + container.scrollLeft),
      });
    }
  }

  function handleAcceptViolation(unitIndex: number, violationIndex: number) {
    const item = itemByUnitIndex.get(unitIndex);
    if (!item) return;

    const id = `${unitIndex}-${violationIndex}`;
    const violation = item.violations[violationIndex];
    const currentText = getCurrentText(item);
    const prob = violation.problematic_text.trim();
    const replacement = getReplacementValue(id, violation.suggested_rewrite).trim();

    if (prob && replacement && currentText.includes(prob)) {
      setParagraphTexts((prev) => ({
        ...prev,
        [unitIndex]: currentText.replace(prob, replacement),
      }));
    }

    setAppliedViolations((prev) => new Set([...prev, id]));
    setSelectedId(null);
  }

  function handleSkipViolation(unitIndex: number, violationIndex: number) {
    const id = `${unitIndex}-${violationIndex}`;
    setSkippedViolations((prev) => new Set([...prev, id]));
    setSelectedId(null);
  }

  function handleEditReplacement(id: string, value: string) {
    setEditedReplacements((prev) => ({ ...prev, [id]: value }));
  }

  function handleCopy() {
    let text = "";
    for (const item of analysisResult.items) {
      text += getCurrentText(item) + "\n\n";
    }
    navigator.clipboard.writeText(text.trim());
  }

  function renderParagraph(item: ParagraphFinding) {
    const currentText = getCurrentText(item);

    if (item.violations.length === 0) {
      const id = `${item.unit_index}-green`;
      const isSelected = selectedId === id;
      return (
        <span
          ref={(el) => { if (el) spanRefs.current[id] = el; }}
          className={`highlight highlight-green ${isSelected ? "highlight-active" : ""}`}
          style={{ cursor: "pointer" }}
          onClick={(e) => { e.stopPropagation(); openPopup(id, e.currentTarget); }}
        >
          {currentText}
        </span>
      );
    }

    const segments = splitByViolations(
      currentText,
      item.violations,
      appliedViolations,
      skippedViolations,
      item.unit_index
    );

    // If all violations have been applied or skipped, no highlights remain —
    // render the paragraph as plain text.
    const hasAnyHighlight = segments.some((s) => s.kind === "violation");
    if (!hasAnyHighlight) {
      return <span>{currentText}</span>;
    }

    return (
      <>
        {segments.map((seg, si) => {
          if (seg.kind === "text") {
            return <span key={si}>{seg.text}</span>;
          }
          const id = `${item.unit_index}-${seg.violationIndex}`;
          const isSelected = selectedId === id;
          return (
            <span
              key={si}
              ref={(el) => { if (el) spanRefs.current[id] = el; }}
              className={`highlight highlight-${seg.severity} ${isSelected ? "highlight-active" : ""}`}
              style={{ cursor: "pointer" }}
              onClick={(e) => { e.stopPropagation(); openPopup(id, e.currentTarget); }}
            >
              {seg.text}
            </span>
          );
        })}
      </>
    );
  }

  function renderPopup() {
    if (!selectedId || !popupPos) return null;

    const parts = selectedId.split("-");
    const unitIndex = parseInt(parts[0], 10);
    const item = itemByUnitIndex.get(unitIndex);
    if (!item) return null;

    const isGreen = parts[1] === "green";
    const violationIndex = isGreen ? -1 : parseInt(parts[1], 10);
    const violation: ViolationDetail | null = violationIndex >= 0 ? item.violations[violationIndex] : null;

    return (
      <div
        className="analysis-popup"
        style={{ top: `${popupPos.top}px`, left: `${popupPos.left}px` }}
        onClick={(e) => e.stopPropagation()}
      >
        {isGreen || !violation ? (
          <>
            <p className="popup-label">✓ Нарушений нет</p>
            {item.overall_comment && <p className="popup-suggestion">{item.overall_comment}</p>}
            <div className="popup-actions popup-actions-single">
              <button className="btn-skip" onClick={() => setSelectedId(null)}>Закрыть</button>
            </div>
          </>
        ) : (
          <>
            <p className="popup-label">
              <span className={`violation-badge violation-${violation.severity}`}>{violation.rule_id}</span>
              {" "}{violation.rule_name}
            </p>
            {violation.comment && <p className="popup-suggestion">{violation.comment}</p>}
            {violation.problematic_text && (
              <div className="popup-rewrite-block">
                <div className="rewrite-row">
                  <span className="rewrite-label">Было:</span>
                  <span className="rewrite-from">«{violation.problematic_text}»</span>
                </div>
                <div className="rewrite-row rewrite-row-edit">
                  <span className="rewrite-label">Стало:</span>
                  <textarea
                    className="rewrite-edit"
                    value={getReplacementValue(selectedId, violation.suggested_rewrite)}
                    onChange={(e) => handleEditReplacement(selectedId, e.target.value)}
                    rows={2}
                    placeholder="Введите замену"
                  />
                </div>
              </div>
            )}
            <div className="popup-actions">
              <button
                className="btn-skip"
                onClick={() => handleSkipViolation(unitIndex, violationIndex)}
              >
                ✕ Пропустить
              </button>
              <button
                className="btn-accept"
                onClick={() => handleAcceptViolation(unitIndex, violationIndex)}
                disabled={!getReplacementValue(selectedId, violation.suggested_rewrite).trim()}
              >
                ✓ Применить
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <div className="analysis-viewer">
      <div className="viewer-header">
        <div className="viewer-title">
          <h3>Результат анализа</h3>
          {sourceTitle && <p className="source-title">{sourceTitle}</p>}
          {sourceUrl && (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="source-url">
              {sourceUrl}
            </a>
          )}
        </div>
        <button className="copy-btn" onClick={handleCopy} title="Скопировать текст">
          📋 Копировать
        </button>
      </div>

      <div className="viewer-content" ref={contentRef}>
        <div className="analysis-text">
          {analysisResult.items.map((item, index) => (
            <span key={item.unit_index}>
              {renderParagraph(item)}
              {index < analysisResult.items.length - 1 && "\n\n"}
            </span>
          ))}
        </div>
        {renderPopup()}
      </div>

      <div className="viewer-summary">
        <div className="summary-stat green-stat">
          <span className="stat-value">{analysisResult.summary.green}</span>
          <span className="stat-label">хорошо</span>
        </div>
        <div className="summary-stat orange-stat">
          <span className="stat-value">{analysisResult.summary.orange}</span>
          <span className="stat-label">требует правок</span>
        </div>
        <div className="summary-stat red-stat">
          <span className="stat-value">{analysisResult.summary.red}</span>
          <span className="stat-label">переписать</span>
        </div>
      </div>
    </div>
  );
}
