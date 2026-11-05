"use client";

import { useRef, useState } from "react";

type Discrepancy = {
  code: string;
  message: string;
  expected?: string | null;
  actual?: string | null;
};

type Evidence = {
  value: string | number | null;
  source_quote: string | null;
  status: "found" | "missing" | "ambiguous";
};

type ExtractedLine = {
  item_code: Evidence;
  description: Evidence;
  quantity: Evidence;
  unit: Evidence;
  unit_price: Evidence;
};

type Result = {
  extraction: {
    extracted_invoice: {
      invoice_number: Evidence;
      supplier_name: Evidence;
      purchase_order_number: Evidence;
      lines: ExtractedLine[];
    };
    review_required: boolean;
    review_reasons: string[];
  };
  reconciliation: {
    invoice_number: string;
    purchase_order_number: string;
    status: string;
    matched_line_count: number;
    discrepancies: Discrepancy[];
  } | null;
};

type SampleData = {
  purchase_order: unknown;
  deliveries: unknown[];
};

const scenarios = [
  {
    id: "partial_delivery",
    label: "Partial delivery and price mismatch",
    documentPath: "/invoice_text.txt",
    recordsPath: "/partial_delivery.json",
  },
  {
    id: "missing_purchase_order",
    label: "Invoice missing purchase order",
    documentPath: "/missing_purchase_order.txt",
    recordsPath: "/missing_purchase_order.json",
  },
];

function EvidenceValue({ label, evidence }: { label: string; evidence: Evidence }) {
  return (
    <div className="evidence-value">
      <div className="evidence-label-row">
        <span className="label">{label}</span>
        <span className={`evidence-status ${evidence.status}`}>{evidence.status}</span>
      </div>
      <strong>{evidence.value ?? "Needs review"}</strong>
      <small>{evidence.source_quote ? `“${evidence.source_quote}”` : "No source quote"}</small>
    </div>
  );
}

const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export default function Home() {
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState(scenarios[0].id);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const activeScenario = scenarios.find((item) => item.id === selectedScenario) ?? scenarios[0];

  function clearSelectedFile() {
    setSelectedFile(null);
    setResult(null);
    setError("");
    if (fileInputRef.current) fileInputRef.current.value = "";
  }

  async function runReview() {
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const sampleResponse = await fetch(activeScenario.recordsPath);
      if (!sampleResponse.ok) throw new Error("Could not load the selected reference records.");
      const sample = (await sampleResponse.json()) as SampleData;
      let documentText: string;

      if (selectedFile) {
        const formData = new FormData();
        formData.append("file", selectedFile);
        let pdfResponse: Response;
        try {
          pdfResponse = await fetch(`${apiBase}/api/invoices/extract-pdf`, {
            method: "POST",
            body: formData,
          });
        } catch {
          throw new Error(`Could not reach the backend at ${apiBase}. Start FastAPI, then retry the PDF.`);
        }
        const pdfResult = (await pdfResponse.json().catch(() => null)) as
          | { document_text?: string; detail?: string }
          | null;
        if (!pdfResponse.ok || !pdfResult?.document_text) {
          throw new Error(pdfResult?.detail ?? `Could not read the PDF (HTTP ${pdfResponse.status}).`);
        }
        documentText = pdfResult.document_text;
      } else {
        const documentResponse = await fetch(activeScenario.documentPath);
        if (!documentResponse.ok) throw new Error("Could not load the selected sample invoice text.");
        documentText = await documentResponse.text();
      }

      let response: Response;
      try {
        response = await fetch(`${apiBase}/api/invoices/reconcile-from-text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            document_text: documentText,
            purchase_order: sample.purchase_order,
            deliveries: sample.deliveries,
          }),
        });
      } catch {
        throw new Error(
          `Could not reach the backend at ${apiBase}. Check that FastAPI is running and OpenRouter is configured.`,
        );
      }
      if (!response.ok) {
        const failure = (await response.json().catch(() => null)) as { detail?: string } | null;
        throw new Error(
          `Invoice extraction failed: ${failure?.detail ?? `HTTP ${response.status}`}. Check the backend and OpenRouter configuration.`,
        );
      }
      setResult((await response.json()) as Result);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The sample review could not be completed.");
    } finally {
      setLoading(false);
    }
  }

  const extracted = result?.extraction.extracted_invoice;
  const reconciliation = result?.reconciliation;

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">m</span><span>mismatch<span className="brand-light">desk</span></span></div>
        <div className="workspace"><span className="workspace-dot" /> DEMO WORKSPACE <span className="chevron">⌄</span></div>
        <nav aria-label="Main navigation">
          <a className="nav-item active" href="#queue"><span>▦</span> Review queue <b>3</b></a>
          <a className="nav-item" href="#documents"><span>▤</span> Documents</a>
          <a className="nav-item" href="#suppliers"><span>◇</span> Suppliers</a>
        </nav>
        <div className="sidebar-bottom"><span className="avatar">FM</span><span><strong>Fatemeh Maddahzadeh</strong><small>Workspace owner</small></span><span className="more">•••</span></div>
      </aside>

      <section className="main-area" id="queue">
        <header className="topbar"><div className="crumb">Operations <span>/</span> Review queue</div><div className="top-actions"><span className="live"><i /> Demo data</span><button className="icon-button" aria-label="Notifications">♧</button></div></header>
        <div className="content">
          <div className="page-heading">
            <div><div className="eyebrow">DEMO OPERATIONS</div><h1>Good morning, Fatemeh</h1><p>Three invoices need a closer look before they move to finance.</p></div>
            <div className="page-actions">
              <label className="scenario-picker">
                <span>{selectedFile ? "Compare against" : "Try a scenario"}</span>
                <select value={selectedScenario} onChange={(event) => { setSelectedScenario(event.target.value); setResult(null); setError(""); }} disabled={loading}>
                  {scenarios.map((scenario) => <option key={scenario.id} value={scenario.id}>{scenario.label}</option>)}
                </select>
              </label>
              <label className="pdf-picker">
                <span>Or upload a PDF</span>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,application/pdf"
                  disabled={loading}
                  onChange={(event) => {
                    const file = event.target.files?.[0] ?? null;
                    if (file && file.size > 10 * 1024 * 1024) {
                      setSelectedFile(null);
                      setError("PDFs must be 10 MB or smaller.");
                      event.target.value = "";
                      return;
                    }
                    setSelectedFile(file);
                    setResult(null);
                    setError("");
                  }}
                />
                <small>Text-based PDFs, up to 10 MB. Scanned PDFs need OCR.</small>
              </label>
              <button className="primary-button" onClick={runReview} disabled={loading}>{loading ? "Extracting and checking…" : selectedFile ? "↻  Extract & review PDF" : "↻  Extract & review sample"}</button>
            </div>
          </div>
          <div className="document-source-note" aria-live="polite">
            <span className="source-icon">▤</span>
            <span className="source-copy">
              <strong>{selectedFile ? `Invoice source: ${selectedFile.name}` : `Demo invoice text: ${activeScenario.documentPath.split("/").pop()}`}</strong>
              <small>{selectedFile ? "This PDF will be converted to text, then extracted and checked against the selected reference records." : "This sample text file will be sent for AI extraction; the selected JSON file supplies purchase order and delivery records."}</small>
            </span>
            {selectedFile && <button type="button" className="source-remove" onClick={clearSelectedFile}>Use sample instead</button>}
          </div>

          {error && <div role="alert" className="error-banner">{error}</div>}

          {result && (
            <section className={`review-outcome ${result.extraction.review_required ? "needs-human" : ""}`} aria-live="polite">
              <div className="outcome-heading">
                <div>
                  <span className="eyebrow">SAMPLE REVIEW RESULT</span>
                  <h2>{result.extraction.review_required ? "Human review required" : `Reconciliation: ${reconciliation?.status ?? "not run"}`}</h2>
                </div>
                <span className={`outcome-pill ${result.extraction.review_required ? "review" : "complete"}`}>
                  {result.extraction.review_required ? "REVIEW EXTRACTION" : reconciliation?.status.replaceAll("_", " ").toUpperCase()}
                </span>
              </div>

              {result.extraction.review_required ? (
                <div className="human-review-message">
                  <strong>Reconciliation was not run.</strong>
                  <p>Check the extracted fields and source evidence before continuing.</p>
                  <ul>{result.extraction.review_reasons.map((reason) => <li key={reason}>{reason}</li>)}</ul>
                </div>
              ) : reconciliation && (
                <div className="reconciliation-summary">
                  <span>Invoice <strong>{reconciliation.invoice_number}</strong></span>
                  <span>Purchase order <strong>{reconciliation.purchase_order_number}</strong></span>
                  <span>Matched lines <strong>{reconciliation.matched_line_count}</strong></span>
                  <span>Discrepancies <strong>{reconciliation.discrepancies.length}</strong></span>
                </div>
              )}

              {extracted && (
                <div className="extraction-panel">
                  <h3>Extracted invoice fields and evidence</h3>
                  <div className="evidence-grid">
                    <EvidenceValue label="INVOICE NUMBER" evidence={extracted.invoice_number} />
                    <EvidenceValue label="SUPPLIER" evidence={extracted.supplier_name} />
                    <EvidenceValue label="PURCHASE ORDER" evidence={extracted.purchase_order_number} />
                  </div>
                  {extracted.lines.map((line, index) => (
                    <div className="extracted-line" key={`${String(line.item_code.value)}-${index}`}>
                      <h4>Invoice line {index + 1}</h4>
                      <div className="evidence-grid line-evidence-grid">
                        <EvidenceValue label="ITEM CODE" evidence={line.item_code} />
                        <EvidenceValue label="DESCRIPTION" evidence={line.description} />
                        <EvidenceValue label="QUANTITY" evidence={line.quantity} />
                        <EvidenceValue label="UNIT" evidence={line.unit} />
                        <EvidenceValue label="UNIT PRICE" evidence={line.unit_price} />
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {reconciliation && (
                <div className="result-discrepancies">
                  <h3>Reconciliation discrepancies</h3>
                  {reconciliation.discrepancies.length === 0 ? (
                    <p className="no-discrepancies">No discrepancies found.</p>
                  ) : (
                    <div className="exception-list">
                      {reconciliation.discrepancies.map((item, index) => (
                        <div className="exception-row" key={`${item.code}-${index}`}>
                          <span className="exception-marker">↔</span>
                          <div className="exception-copy"><strong>{item.code.replaceAll("_", " ")}</strong><span>{item.message}</span></div>
                          <div className="comparison"><span>{item.expected ? `Expected ${item.expected}` : "Purchase record"}</span><b>{item.actual ? `Invoice ${item.actual}` : "Review match"}</b></div>
                          <span className="review-tag">CHECK</span>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

          <div className="stats-grid">
            <article className="stat-card"><span>NEEDS REVIEW</span><strong>03</strong><small><i className="orange-dot" /> 2 new today</small></article>
            <article className="stat-card"><span>READY TO MATCH</span><strong>12</strong><small><i className="green-dot" /> Across 5 suppliers</small></article>
            <article className="stat-card"><span>AVG. REVIEW TIME</span><strong>4.2 <em>min</em></strong><small><i className="blue-dot" /> This week</small></article>
          </div>

          <div className="section-title"><div><h2>Priority review</h2><p>Exceptions are grouped by the records they need checked against.</p></div><button className="text-button">View all cases <span>→</span></button></div>

          <article className="case-card">
            <div className="case-top"><div className="supplier-avatar">TC</div><div className="case-identity"><strong>Torino Components</strong><span>Invoice INV-1042 <i>·</i> Received today, 09:41</span></div><span className="status-pill"><i /> NEEDS REVIEW</span><button className="more-button" aria-label="More options">•••</button></div>
            <div className="case-summary"><div><span className="label">REFERENCE</span><strong>PO-778 <span className="muted">·</span> Delivery DN-900</strong></div><div><span className="label">INVOICE TOTAL</span><strong>€ 1,250.00</strong></div><div><span className="label">MATCHED LINES</span><strong>{reconciliation ? `${reconciliation.matched_line_count} of 1` : "— of 1"}</strong></div></div>
            <div className="exception-heading"><span className="warning-icon">!</span><strong>{reconciliation ? `${reconciliation.discrepancies.length} differences found` : result ? "Awaiting extraction review" : "Two differences found"}</strong><span className="small-muted">Invoice ↔ Purchase records</span></div>
            <div className="exception-list">
              {reconciliation?.discrepancies.map((item, index) => <div className="exception-row" key={`${item.code}-${index}`}><span className="exception-marker">↔</span><div className="exception-copy"><strong>{item.code.replaceAll("_", " ")}</strong><span>{item.message}</span></div><div className="comparison"><span>{item.expected ? `Expected ${item.expected}` : "Purchase record"}</span><b>{item.actual ? `Invoice ${item.actual}` : "Review match"}</b></div><span className="review-tag">CHECK</span></div>)}
              {!result && <><div className="exception-row"><span className="exception-marker">↔</span><div className="exception-copy"><strong>Billed quantity exceeds delivery</strong><span>Invoice bills 100 units; delivery record shows 80.</span></div><div className="comparison"><span>Received 80</span><b>Invoiced 100</b></div><span className="review-tag">CHECK</span></div><div className="exception-row"><span className="exception-marker">↔</span><div className="exception-copy"><strong>Unit price differs from order</strong><span>Invoice price is higher than the agreed purchase price.</span></div><div className="comparison"><span>Order €12.00</span><b>Invoice €12.50</b></div><span className="review-tag">CHECK</span></div></>}
            </div>
            <div className="case-footer"><span>Reconciled against <strong>1 purchase order</strong> and <strong>1 delivery record</strong></span><button className="review-button">Open case <span>→</span></button></div>
          </article>

          <div className="lower-grid">
            <article className="mini-card"><div className="mini-heading"><h3>Recent activity</h3><button className="text-button">See history →</button></div><div className="activity-item"><span className="activity-icon green">✓</span><div><strong>INV-1039 matched successfully</strong><small>Alpina Packaging · 28 min ago</small></div><span className="activity-amount">€ 842.30</span></div><div className="activity-item"><span className="activity-icon amber">!</span><div><strong>INV-1041 sent for review</strong><small>Officina Riva · 1 hour ago</small></div><span className="activity-amount">€ 2,140.00</span></div><div className="activity-item"><span className="activity-icon blue">↻</span><div><strong>INV-1037 updated by reviewer</strong><small>Nord Est Tools · 2 hours ago</small></div><span className="activity-amount">€ 316.80</span></div></article>
            <article className="insight-card"><div className="insight-icon">✳</div><span className="label">WHY THIS CASE?</span><h3>Two checks caught it early.</h3><p>The quantity check compares billed units to recorded deliveries. The price check compares the invoice to the agreed order price.</p><div className="insight-foot"><span><i /> Rules-based checks</span><span>Details →</span></div></article>
          </div>
          <footer className="disclaimer">DEMO WORKSPACE <span>·</span> Synthetic records for demonstration only</footer>
        </div>
      </section>
    </main>
  );
}
