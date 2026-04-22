import { useEffect, useId, useRef, useState } from "react";
import type { AnalysisResponse, ParagraphFinding, ViolationDetail } from "../api/client";

type Segment =
  | { kind: "text"; text: string }
  | { kind: "violation"; text: string; violationIndex: number; severity: string };

const SEVERITY_LABEL_RU: Record<string, string> = {
  green: "незначительное",
  orange: "умеренное",
  red: "серьёзное",
};

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
  const [editedReplacements, setEditedReplacements] = useState<Record<string, string>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [popupPos, setPopupPos] = useState<{ top: number; left: number } | null>(null);
  const [actionMessage, setActionMessage] = useState<string>("");

  const contentRef = useRef<HTMLDivElement>(null);
  const spanRefs = useRef<Record<string, HTMLSpanElement | null>>({});
  const popupRef = useRef<HTMLDivElement>(null);
  const firstFocusableRef = useRef<HTMLElement | null>(null);
  const popupLabelId = useId();
  const popupDescId = useId();

  const itemByUnitIndex = new Map<number, ParagraphFinding>(
    analysisResult.items.map((item) => [item.unit_index, item])
  );

  function getCurrentText(item: ParagraphFinding): string {
    return paragraphTexts[item.unit_index] ?? item.source_text;
  }

  function getReplacementValue(id: string, fallback: string): string {
    return editedReplacements[id] ?? fallback;
  }

  function closePopup() {
    const previouslySelected = selectedId;
    setSelectedId(null);
    if (previouslySelected) {
      const trigger = spanRefs.current[previouslySelected];
      if (trigger) trigger.focus();
    }
  }

  useEffect(() => {
    if (selectedId === null) return;

    function handleOutsideClick(e: MouseEvent) {
      const popup = popupRef.current;
      if (popup && popup.contains(e.target as Node)) return;
      const trigger = spanRefs.current[selectedId!];
      if (trigger && trigger.contains(e.target as Node)) return;
      setSelectedId(null);
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        closePopup();
      }
    }

    document.addEventListener("click", handleOutsideClick);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("click", handleOutsideClick);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [selectedId]);

  useEffect(() => {
    if (selectedId === null) return;
    const target = firstFocusableRef.current;
    if (target) {
      const timer = window.setTimeout(() => target.focus(), 0);
      return () => window.clearTimeout(timer);
    }
  }, [selectedId]);

  function openPopup(id: string, spanEl: HTMLSpanElement) {
    if (selectedId === id) {
      closePopup();
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
    setActionMessage(`Замена применена: «${prob}» заменено на «${replacement}».`);
    closePopup();
  }

  function handleSkipViolation(unitIndex: number, violationIndex: number) {
    const id = `${unitIndex}-${violationIndex}`;
    const item = itemByUnitIndex.get(unitIndex);
    const prob = item?.violations[violationIndex]?.problematic_text ?? "";
    setSkippedViolations((prev) => new Set([...prev, id]));
    setActionMessage(`Пропущено замечание для фрагмента «${prob}».`);
    closePopup();
  }

  function handleEditReplacement(id: string, value: string) {
    setEditedReplacements((prev) => ({ ...prev, [id]: value }));
  }

  function handleCopy() {
    let text = "";
    for (const item of analysisResult.items) {
      text += getCurrentText(item) + "\n\n";
    }
    navigator.clipboard.writeText(text.trim()).then(
      () => setActionMessage("Текст скопирован в буфер обмена."),
      () => setActionMessage("Не удалось скопировать текст."),
    );
  }

  function triggerAriaLabel(
    violation: ViolationDetail,
    text: string,
    unitIndex: number,
  ): string {
    const severity = SEVERITY_LABEL_RU[violation.severity] ?? violation.severity;
    return (
      `Замечание ${severity}. ${violation.rule_name}. ` +
      `Фрагмент: ${text}. Абзац ${unitIndex + 1}. ` +
      `Нажмите Enter, чтобы открыть подробности и варианты замены.`
    );
  }

  function renderParagraph(item: ParagraphFinding) {
    const currentText = getCurrentText(item);

    if (item.violations.length === 0) {
      const id = `${item.unit_index}-green`;
      const isSelected = selectedId === id;
      return (
        <span
          ref={(el) => { if (el) spanRefs.current[id] = el; }}
          role="button"
          tabIndex={0}
          aria-haspopup="dialog"
          aria-expanded={isSelected}
          aria-label={`Абзац ${item.unit_index + 1}. Нарушений нет. Нажмите Enter для подробностей.`}
          className={`highlight highlight-green ${isSelected ? "highlight-active" : ""}`}
          onClick={(e) => { e.stopPropagation(); openPopup(id, e.currentTarget); }}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              openPopup(id, e.currentTarget);
            }
          }}
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
          const violation = item.violations[seg.violationIndex];
          return (
            <span
              key={si}
              ref={(el) => { if (el) spanRefs.current[id] = el; }}
              role="button"
              tabIndex={0}
              aria-haspopup="dialog"
              aria-expanded={isSelected}
              aria-label={triggerAriaLabel(violation, seg.text, item.unit_index)}
              className={`highlight highlight-${seg.severity} ${isSelected ? "highlight-active" : ""}`}
              onClick={(e) => { e.stopPropagation(); openPopup(id, e.currentTarget); }}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  openPopup(id, e.currentTarget);
                }
              }}
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
        ref={popupRef}
        className="analysis-popup"
        style={{ top: `${popupPos.top}px`, left: `${popupPos.left}px` }}
        role="dialog"
        aria-modal="false"
        aria-labelledby={popupLabelId}
        aria-describedby={popupDescId}
        onClick={(e) => e.stopPropagation()}
      >
        {isGreen || !violation ? (
          <>
            <p className="popup-label" id={popupLabelId}>
              <span aria-hidden="true">✓ </span>Нарушений нет
            </p>
            {item.overall_comment ? (
              <p className="popup-suggestion" id={popupDescId}>{item.overall_comment}</p>
            ) : (
              <p id={popupDescId} className="sr-only">Для этого абзаца замечаний не найдено.</p>
            )}
            <div className="popup-actions popup-actions-single">
              <button
                type="button"
                className="btn-skip"
                ref={(el) => { firstFocusableRef.current = el; }}
                onClick={closePopup}
              >
                Закрыть
              </button>
            </div>
          </>
        ) : (
          <>
            <p className="popup-label" id={popupLabelId}>
              <span className={`violation-badge violation-${violation.severity}`}>
                {violation.rule_id}
                <span className="sr-only"> — {SEVERITY_LABEL_RU[violation.severity] ?? violation.severity}</span>
              </span>
              {" "}{violation.rule_name}
            </p>
            {violation.comment ? (
              <p className="popup-suggestion" id={popupDescId}>{violation.comment}</p>
            ) : (
              <p id={popupDescId} className="sr-only">Пояснения нет.</p>
            )}
            {violation.problematic_text && (
              <div className="popup-rewrite-block">
                <div className="rewrite-row">
                  <span className="rewrite-label" id={`${popupLabelId}-was`}>Было</span>
                  <span className="rewrite-from" aria-labelledby={`${popupLabelId}-was`}>
                    «{violation.problematic_text}»
                  </span>
                </div>
                <div className="rewrite-row rewrite-row-edit">
                  <label className="rewrite-label" htmlFor={`${popupLabelId}-edit`}>
                    Стало (можно отредактировать)
                  </label>
                  <textarea
                    id={`${popupLabelId}-edit`}
                    ref={(el) => { firstFocusableRef.current = el; }}
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
                type="button"
                className="btn-skip"
                onClick={() => handleSkipViolation(unitIndex, violationIndex)}
                aria-label="Пропустить замечание и убрать выделение"
              >
                <span aria-hidden="true">✕ </span>Пропустить
              </button>
              <button
                type="button"
                className="btn-accept"
                onClick={() => handleAcceptViolation(unitIndex, violationIndex)}
                disabled={!getReplacementValue(selectedId, violation.suggested_rewrite).trim()}
                aria-label="Применить предложенную замену в тексте"
              >
                <span aria-hidden="true">✓ </span>Применить
              </button>
            </div>
          </>
        )}
      </div>
    );
  }

  return (
    <section className="analysis-viewer panel" aria-labelledby="analysis-heading">
      <div className="viewer-header">
        <div className="viewer-title">
          <h2 id="analysis-heading">Результат анализа</h2>
          {sourceTitle && <p className="source-title">{sourceTitle}</p>}
          {sourceUrl && (
            <a href={sourceUrl} target="_blank" rel="noopener noreferrer" className="source-url">
              {sourceUrl}
              <span className="sr-only"> (открывается в новой вкладке)</span>
            </a>
          )}
        </div>
        <button
          type="button"
          className="copy-btn"
          onClick={handleCopy}
          aria-label="Скопировать обработанный текст в буфер обмена"
        >
          <span aria-hidden="true">📋 </span>Копировать
        </button>
      </div>

      <div role="status" aria-live="polite" aria-atomic="true" className="sr-only">
        {actionMessage}
      </div>

      <div className="viewer-content" ref={contentRef}>
        <p className="sr-only">
          В тексте ниже выделены фрагменты с замечаниями. Переходите по ним клавишей Tab, открывайте подробности клавишей Enter. Закрыть окно замечания — Escape.
        </p>
        <div className="analysis-text" aria-label="Размеченный текст с замечаниями">
          {analysisResult.items.map((item, index) => (
            <span key={item.unit_index}>
              {renderParagraph(item)}
              {index < analysisResult.items.length - 1 && "\n\n"}
            </span>
          ))}
        </div>
        {renderPopup()}
      </div>

      <dl className="viewer-summary" aria-label="Сводка по результатам">
        <div className="summary-stat green-stat">
          <dt className="stat-label">Хорошо</dt>
          <dd className="stat-value">{analysisResult.summary.green}</dd>
        </div>
        <div className="summary-stat orange-stat">
          <dt className="stat-label">Требует правок</dt>
          <dd className="stat-value">{analysisResult.summary.orange}</dd>
        </div>
        <div className="summary-stat red-stat">
          <dt className="stat-label">Переписать</dt>
          <dd className="stat-value">{analysisResult.summary.red}</dd>
        </div>
      </dl>
    </section>
  );
}
