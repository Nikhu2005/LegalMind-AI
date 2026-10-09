import { useState } from "react";

import {
  LayoutDashboard,
  Search,
  Scale,
  FileText,
  GitCompare,
  Library,
  BarChart3,
  Settings,
  Bell,
  ChevronDown,
  Upload,
  ArrowUpRight,
  Clock3,
  BookOpen,
  CheckCircle2,
  AlertCircle,
  Loader2,
  X,
  ArrowLeft,
  SlidersHorizontal,
  RotateCcw,
  ExternalLink,
} from "lucide-react";

const COURT_OPTIONS = [
  { value: "", label: "All Courts" },
  { value: "Supreme Court of India", label: "Supreme Court of India" },
  { value: "High Court", label: "High Courts" },
  { value: "District Court", label: "District Courts" },
];

const DOCUMENT_TYPE_OPTIONS = [
  { value: "", label: "All Document Types" },
  { value: "judgment", label: "Judgment" },
  { value: "order", label: "Order" },
  { value: "petition", label: "Petition" },
];

const LANGUAGE_OPTIONS = [
  { value: "English", label: "English" },
  { value: "Hindi", label: "Hindi — हिन्दी" },
  { value: "Marathi", label: "Marathi — मराठी" },
  { value: "Gujarati", label: "Gujarati — ગુજરાતી" },
  { value: "Bengali", label: "Bengali — বাংলা" },
  { value: "Tamil", label: "Tamil — தமிழ்" },
  { value: "Telugu", label: "Telugu — తెలుగు" },
  { value: "Kannada", label: "Kannada — ಕನ್ನಡ" },
  { value: "Punjabi", label: "Punjabi — ਪੰਜਾਬੀ" },
];

const SELECT_CLASS =
  "w-full rounded-xl border border-slate-200 bg-white px-3.5 py-3 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100";

function App() {
  const [activePage, setActivePage] = useState("Dashboard");
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [analysisResult, setAnalysisResult] = useState(null);
  const [similarResults, setSimilarResults] = useState(null);
  const [error, setError] = useState("");

  const [searchQuestion, setSearchQuestion] = useState("");
  const [searchCourt, setSearchCourt] = useState("");
  const [searchDocumentType, setSearchDocumentType] = useState("");
  const [searchTopK, setSearchTopK] = useState(10);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchResults, setSearchResults] = useState(null);

  const [askQuestion, setAskQuestion] = useState("");
  const [askCourt, setAskCourt] = useState("");
  const [askDocumentType, setAskDocumentType] = useState("");
  const [askTopK, setAskTopK] = useState(5);
  const [askLoading, setAskLoading] = useState(false);
  const [askResult, setAskResult] = useState(null);

  const [compareCases, setCompareCases] = useState([]);
  const [compareCaseA, setCompareCaseA] = useState("");
  const [compareCaseB, setCompareCaseB] = useState("");
  const [compareLoading, setCompareLoading] = useState(false);
  const [compareResult, setCompareResult] = useState(null);
  const [compareCasesLoading, setCompareCasesLoading] = useState(false);

  const [legalDocuments, setLegalDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(false);
  const [documentsSearch, setDocumentsSearch] = useState("");
  const [documentsCourt, setDocumentsCourt] = useState("");
  const [documentsType, setDocumentsType] = useState("");
  const [selectedDocument, setSelectedDocument] = useState(null);

  const [uploadCaseA, setUploadCaseA] = useState(null);
  const [uploadCaseB, setUploadCaseB] = useState(null);
  const [uploadCompareLoading, setUploadCompareLoading] = useState(false);
  const [uploadCompareResult, setUploadCompareResult] = useState(null);

  /* ------------------------------------------------------------------ */
  /* Data loaders                                                        */
  /* ------------------------------------------------------------------ */

  const loadCompareCases = async (force = false) => {
    if (force !== true && compareCases.length > 0) return;

    setCompareCasesLoading(true);
    setError("");

    try {
      const response = await fetch("/api/cases");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load cases.");
      }

      setCompareCases(data.cases || []);
    } catch (requestError) {
      setError(requestError.message || "Could not load cases.");
    } finally {
      setCompareCasesLoading(false);
    }
  };

  const loadLegalDocuments = async (force = false) => {
    if (force !== true && legalDocuments.length > 0) return;

    setDocumentsLoading(true);
    setError("");

    try {
      const response = await fetch("/api/cases");
      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not load legal documents.");
      }

      setLegalDocuments(data.cases || []);
    } catch (requestError) {
      setError(
        requestError.message ||
          "Could not connect to the LegalMind knowledge base."
      );
    } finally {
      setDocumentsLoading(false);
    }
  };

  /* ------------------------------------------------------------------ */
  /* Compare                                                             */
  /* ------------------------------------------------------------------ */

  const compareSelectedCases = async () => {
    if (!compareCaseA || !compareCaseB) {
      setError("Please select both cases.");
      return;
    }

    if (compareCaseA === compareCaseB) {
      setError("Please select two different cases.");
      return;
    }

    setCompareLoading(true);
    setCompareResult(null);
    setError("");

    try {
      const response = await fetch("/api/compare-cases", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          case1_key: compareCaseA,
          case2_key: compareCaseB,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Case comparison failed.");
      }

      setCompareResult(data);
    } catch (requestError) {
      setError(requestError.message || "Case comparison failed.");
    } finally {
      setCompareLoading(false);
    }
  };

  const handleComparePdfChange = (event, caseType) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Only PDF files are supported.");
      return;
    }

    setError("");

    if (caseType === "A") {
      setUploadCaseA(file);
    } else {
      setUploadCaseB(file);
    }

    setUploadCompareResult(null);
  };

  const compareUploadedCases = async () => {
    if (!uploadCaseA || !uploadCaseB) {
      setError("Please upload both Case A and Case B PDFs.");
      return;
    }

    if (
      uploadCaseA.name === uploadCaseB.name &&
      uploadCaseA.size === uploadCaseB.size
    ) {
      setError("Please upload two different PDF files.");
      return;
    }

    setUploadCompareLoading(true);
    setUploadCompareResult(null);
    setError("");

    try {
      const formData = new FormData();
      formData.append("case_a", uploadCaseA);
      formData.append("case_b", uploadCaseB);

      const response = await fetch("/api/compare-uploaded-cases", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Uploaded case comparison failed.");
      }

      setUploadCompareResult(data);
    } catch (requestError) {
      setError(
        requestError.message || "Could not compare the uploaded cases."
      );
    } finally {
      setUploadCompareLoading(false);
    }
  };

  /* ------------------------------------------------------------------ */
  /* Navigation + file handling                                          */
  /* ------------------------------------------------------------------ */

  const navigate = (page) => {
    setActivePage(page);
    setError("");

    if (page === "Legal Documents" && legalDocuments.length === 0) {
      loadLegalDocuments();
    }
  };

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];

    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setError("Please select a PDF file.");
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
    setAnalysisResult(null);
    setSimilarResults(null);
    setError("");
  };

  const clearSelectedFile = () => {
    setSelectedFile(null);
    setAnalysisResult(null);
    setSimilarResults(null);
    setError("");
  };

  /* ------------------------------------------------------------------ */
  /* Search / Ask / Analyze                                              */
  /* ------------------------------------------------------------------ */

  const searchCaseLaw = async () => {
    const question = searchQuestion.trim();

    if (!question) {
      setError("Please enter a legal question or topic to search.");
      return;
    }

    setSearchLoading(true);
    setError("");
    setSearchResults(null);

    try {
      const response = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          top_k: Number(searchTopK),
          court: searchCourt || null,
          document_type: searchDocumentType || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Legal search failed.");
      }

      setSearchResults(data);
    } catch (requestError) {
      setError(
        requestError.message ||
          "Could not connect to the LegalMind search service."
      );
    } finally {
      setSearchLoading(false);
    }
  };

  const resetCaseLawSearch = () => {
    setSearchQuestion("");
    setSearchCourt("");
    setSearchDocumentType("");
    setSearchTopK(10);
    setSearchResults(null);
    setError("");
  };

  const askLegalMind = async () => {
    const question = askQuestion.trim();

    if (!question) {
      setError("Please enter a legal question first.");
      return;
    }

    setAskLoading(true);
    setError("");
    setAskResult(null);

    try {
      const response = await fetch("/api/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question,
          top_k: Number(askTopK),
          court: askCourt || null,
          document_type: askDocumentType || null,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Legal question failed.");
      }

      setAskResult(data);
    } catch (requestError) {
      setError(requestError.message || "Could not connect to LegalMind AI.");
    } finally {
      setAskLoading(false);
    }
  };

  const analyzeCurrentCase = async () => {
    if (!selectedFile) {
      setError("Please select a PDF case document first.");
      return;
    }

    setLoading(true);
    setError("");
    setAnalysisResult(null);
    setSimilarResults(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch("/api/upload-current-case", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Case analysis failed.");
      }

      setAnalysisResult(data);
    } catch (requestError) {
      setError(requestError.message || "Could not connect to LegalMind AI.");
    } finally {
      setLoading(false);
    }
  };

  const findSimilarJudgments = async () => {
    if (!selectedFile) {
      setError("Please select a PDF case document first.");
      return;
    }

    setSimilarLoading(true);
    setError("");
    setSimilarResults(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch("/api/find-similar-judgments", {
        method: "POST",
        body: formData,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Could not find similar judgments.");
      }

      setSimilarResults(data);
    } catch (requestError) {
      setError(requestError.message || "Similar judgment search failed.");
    } finally {
      setSimilarLoading(false);
    }
  };

  /* ------------------------------------------------------------------ */
  /* Pages                                                               */
  /* ------------------------------------------------------------------ */

  const renderDashboard = () => (
    <>
      <PageHeader
        eyebrow="Legal Research Workspace"
        title="Good evening"
        description="Search Indian case law, analyze legal documents, and discover relevant judgments with AI-powered research."
        buttonText="Analyze New Case"
        buttonIcon={<Upload size={17} />}
        onButtonClick={() => navigate("Analyze Current Case")}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          title="Indexed Cases"
          value="4"
          subtitle="Indian court judgments"
          icon={<Scale size={19} />}
          trend="Knowledge base"
        />
        <StatCard
          title="Legal Documents"
          value="965+"
          subtitle="Indexed passages"
          icon={<FileText size={19} />}
          trend="Indexed"
        />
        <StatCard
          title="AI Searches"
          value="128"
          subtitle="Research queries"
          icon={<Search size={19} />}
          trend="Research activity"
        />
        <StatCard
          title="System Status"
          value="Online"
          subtitle="AI services operational"
          icon={<ArrowUpRight size={19} />}
          trend="All systems normal"
          online
        />
      </div>

      <div className="mt-6 grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-start justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                Start Legal Research
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Choose a research workflow to get started.
              </p>
            </div>
            <div className="rounded-xl bg-blue-50 p-2.5 text-blue-700">
              <BookOpen size={20} />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <ResearchCard
              icon={<Search size={20} />}
              title="Search Case Law"
              description="Find relevant judgments using semantic and keyword search."
              onClick={() => navigate("Case Law Search")}
            />
            <ResearchCard
              icon={<Scale size={20} />}
              title="Ask LegalMind"
              description="Ask questions and receive grounded answers from legal documents."
              onClick={() => navigate("Ask LegalMind")}
            />
            <ResearchCard
              icon={<FileText size={20} />}
              title="Analyze Current Case"
              description="Extract legal issues, Acts, sections, facts and concepts."
              onClick={() => navigate("Analyze Current Case")}
            />
            <ResearchCard
              icon={<GitCompare size={20} />}
              title="Compare Cases"
              description="Compare facts, issues, reasoning and decisions across cases."
              onClick={() => navigate("Compare Cases")}
            />
          </div>
        </section>

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex items-center justify-between">
            <div>
              <h3 className="text-lg font-bold text-slate-900">
                Recent Research
              </h3>
              <p className="mt-1 text-sm text-slate-500">
                Your latest legal research activity.
              </p>
            </div>
            <Clock3 size={19} className="text-slate-400" />
          </div>

          <div className="space-y-1">
            <ActivityItem
              title="Similar judgment analysis"
              description="Current case research"
              time="Today"
              icon={<Scale size={16} />}
            />
            <ActivityItem
              title="Case law search"
              description="Supreme Court judgments"
              time="Today"
              icon={<Search size={16} />}
            />
            <ActivityItem
              title="Legal document analysis"
              description="PDF document processed"
              time="Yesterday"
              icon={<FileText size={16} />}
            />
            <ActivityItem
              title="Case comparison"
              description="Two judgments compared"
              time="Yesterday"
              icon={<GitCompare size={16} />}
            />
          </div>
        </section>
      </div>

      <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <h3 className="text-lg font-bold text-slate-900">
            Legal Knowledge Base
          </h3>
          <p className="mt-1 text-sm text-slate-500">
            Current indexed legal research sources.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-3">
          <KnowledgeCard
            court="Supreme Court of India"
            cases="4"
            type="Judgments"
          />
          <KnowledgeCard
            court="High Courts"
            cases="Coming soon"
            type="Judgments"
          />
          <KnowledgeCard
            court="District Courts"
            cases="Coming soon"
            type="Judgments"
          />
        </div>
      </section>
    </>
  );

  const renderAnalyzePage = () => (
    <>
      <PageHeader
        eyebrow="Case Intelligence"
        title="Analyze Current Case"
        description="Upload a legal PDF and LegalMind AI will extract legal issues, Acts, sections, facts, arguments and concepts."
      />

      <div className="max-w-5xl">
        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-6">
            <h3 className="text-lg font-bold text-slate-900">
              Upload Legal Document
            </h3>
            <p className="mt-1 text-sm text-slate-500">
              Currently supported format: PDF
            </p>
          </div>

          {!selectedFile && (
            <label className="group flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-16 text-center transition hover:border-blue-400 hover:bg-blue-50/30">
              <div className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-100 text-blue-700">
                <Upload size={25} />
              </div>

              <h4 className="text-base font-bold text-slate-800">
                Upload your case PDF
              </h4>

              <p className="mt-2 text-sm text-slate-500">
                Click to browse your computer
              </p>

              <span className="mt-4 rounded-lg bg-white px-4 py-2 text-xs font-semibold text-blue-700 shadow-sm">
                Choose PDF
              </span>

              <input
                type="file"
                accept=".pdf,application/pdf"
                className="hidden"
                onChange={handleFileChange}
              />
            </label>
          )}

          {selectedFile && (
            <div className="rounded-2xl border border-blue-100 bg-blue-50/50 p-5">
              <div className="flex items-center gap-4">
                <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-white text-blue-700 shadow-sm">
                  <FileText size={22} />
                </div>

                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-bold text-slate-800">
                    {selectedFile.name}
                  </p>
                  <p className="mt-1 text-xs text-slate-500">
                    {(selectedFile.size / 1024 / 1024).toFixed(2)} MB
                  </p>
                </div>

                <button
                  type="button"
                  onClick={clearSelectedFile}
                  className="rounded-lg p-2 text-slate-400 transition hover:bg-white hover:text-red-500"
                >
                  <X size={18} />
                </button>
              </div>

              <button
                type="button"
                onClick={analyzeCurrentCase}
                disabled={loading}
                className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {loading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Analyzing Case...
                  </>
                ) : (
                  <>
                    <Scale size={18} />
                    Analyze Case with LegalMind AI
                  </>
                )}
              </button>
            </div>
          )}

          {error && (
            <div className="mt-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </section>

        {analysisResult && (
          <>
            <CaseAnalysisResult result={analysisResult} />

            <section className="mt-6 rounded-2xl border border-blue-100 bg-white p-6 shadow-sm">
              <div className="flex flex-col justify-between gap-5 md:flex-row md:items-center">
                <div>
                  <h3 className="text-lg font-bold text-slate-900">
                    Find Similar Judgments
                  </h3>
                  <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
                    Search the LegalMind AI knowledge base for previous
                    judgments with similar legal issues, Acts, sections and
                    legal concepts.
                  </p>
                </div>

                <button
                  type="button"
                  onClick={findSimilarJudgments}
                  disabled={similarLoading}
                  className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {similarLoading ? (
                    <>
                      <Loader2 size={18} className="animate-spin" />
                      Searching Judgments...
                    </>
                  ) : (
                    <>
                      <Search size={18} />
                      Find Similar Judgments
                    </>
                  )}
                </button>
              </div>
            </section>

            {similarResults && (
              <SimilarJudgmentsResult result={similarResults} />
            )}
          </>
        )}
      </div>
    </>
  );

  const renderCaseLawSearchPage = () => (
    <>
      <PageHeader
        eyebrow="Legal Research"
        title="Case Law Search"
        description="Find relevant Indian judgments using hybrid semantic and keyword retrieval across the LegalMind AI knowledge base."
      />

      <section className="max-w-6xl overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 bg-gradient-to-r from-blue-50/80 to-white px-6 py-5">
          <div className="flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-700 text-white shadow-sm">
                <Search size={21} />
              </div>
              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Search the Legal Knowledge Base
                </h3>
                <p className="mt-1 text-sm leading-6 text-slate-500">
                  Search by legal question, issue, Act, section, doctrine, or
                  case-law topic.
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2 rounded-full border border-blue-100 bg-white px-3 py-1.5 text-[11px] font-bold text-blue-700 shadow-sm">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Hybrid Retrieval Active
            </div>
          </div>
        </div>

        <div className="p-6">
          <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4">
            <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
              Legal Question or Search Topic
            </label>

            <div className="flex flex-col gap-3 lg:flex-row">
              <div className="relative flex-1">
                <Search
                  size={19}
                  className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
                />
                <input
                  value={searchQuestion}
                  onChange={(event) => setSearchQuestion(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" && !searchLoading) {
                      searchCaseLaw();
                    }
                  }}
                  placeholder="e.g. natural justice in termination of service"
                  className="w-full rounded-xl border border-slate-200 bg-white py-3.5 pl-11 pr-4 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                />
              </div>

              <button
                type="button"
                onClick={searchCaseLaw}
                disabled={searchLoading}
                className="inline-flex min-w-[155px] items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {searchLoading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    Searching...
                  </>
                ) : (
                  <>
                    <Search size={18} />
                    Search Cases
                  </>
                )}
              </button>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
              <p className="text-[11px] text-slate-400">
                Press Enter to search. Use filters to narrow the research scope.
              </p>
              <span className="text-[11px] font-medium text-slate-400">
                Semantic + keyword retrieval
              </span>
            </div>
          </div>

          <div className="mt-5 flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-500">
            <SlidersHorizontal size={14} className="text-blue-600" />
            Search Filters
          </div>

          <div className="mt-3 grid gap-4 md:grid-cols-3">
            <div>
              <label className="mb-2 block text-xs font-semibold text-slate-500">
                Court
              </label>
              <select
                value={searchCourt}
                onChange={(event) => setSearchCourt(event.target.value)}
                className={SELECT_CLASS}
              >
                {COURT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold text-slate-500">
                Document Type
              </label>
              <select
                value={searchDocumentType}
                onChange={(event) => setSearchDocumentType(event.target.value)}
                className={SELECT_CLASS}
              >
                {DOCUMENT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="mb-2 block text-xs font-semibold text-slate-500">
                Maximum Results
              </label>
              <select
                value={searchTopK}
                onChange={(event) => setSearchTopK(Number(event.target.value))}
                className={SELECT_CLASS}
              >
                <option value={5}>Top 5</option>
                <option value={10}>Top 10</option>
                <option value={15}>Top 15</option>
                <option value={20}>Top 20</option>
              </select>
            </div>
          </div>

          <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-center gap-2 text-xs text-slate-400">
              <Search size={14} />
              <span>
                Searches indexed legal passages and returns the most relevant
                matches.
              </span>
            </div>

            <button
              type="button"
              onClick={resetCaseLawSearch}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
            >
              <RotateCcw size={14} />
              Reset Search
            </button>
          </div>

          {error && activePage === "Case Law Search" && (
            <div className="mt-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}
        </div>
      </section>

      {searchResults && <CaseLawSearchResults result={searchResults} />}
    </>
  );

  const renderAskLegalMindPage = () => (
    <>
      <PageHeader
        eyebrow="AI Legal Research"
        title="Ask LegalMind"
        description="Ask legal research questions and receive grounded answers generated from the indexed legal knowledge base."
      />

      <section className="max-w-6xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex items-start gap-3">
          <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
            <Scale size={22} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              Ask a Legal Question
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              LegalMind retrieves relevant case-law passages, reranks them, and
              uses Gemini to generate a source-grounded research answer.
            </p>
          </div>
        </div>

        <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4">
          <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
            Your Legal Question
          </label>

          <textarea
            value={askQuestion}
            onChange={(event) => setAskQuestion(event.target.value)}
            onKeyDown={(event) => {
              if (
                (event.ctrlKey || event.metaKey) &&
                event.key === "Enter" &&
                !askLoading
              ) {
                askLegalMind();
              }
            }}
            placeholder="e.g. What principles of natural justice apply before termination of a public employee?"
            rows={5}
            className="w-full resize-y rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
          />

          <div className="mt-3 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <p className="text-[11px] text-slate-400">
              Tip: Ctrl + Enter to ask. Keep questions specific for better
              retrieval.
            </p>

            <button
              type="button"
              onClick={askLegalMind}
              disabled={askLoading}
              className="inline-flex min-w-[170px] items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {askLoading ? (
                <>
                  <Loader2 size={18} className="animate-spin" />
                  Researching...
                </>
              ) : (
                <>
                  <Scale size={18} />
                  Ask LegalMind
                </>
              )}
            </button>
          </div>
        </div>

        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <div>
            <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
              Court
            </label>
            <select
              value={askCourt}
              onChange={(event) => setAskCourt(event.target.value)}
              className={SELECT_CLASS}
            >
              {COURT_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
              Document Type
            </label>
            <select
              value={askDocumentType}
              onChange={(event) => setAskDocumentType(event.target.value)}
              className={SELECT_CLASS}
            >
              {DOCUMENT_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
              Source Passages
            </label>
            <select
              value={askTopK}
              onChange={(event) => setAskTopK(Number(event.target.value))}
              className={SELECT_CLASS}
            >
              <option value={3}>Top 3</option>
              <option value={5}>Top 5</option>
              <option value={8}>Top 8</option>
              <option value={10}>Top 10</option>
            </select>
          </div>
        </div>

        {error && activePage === "Ask LegalMind" && (
          <div className="mt-5 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </section>

      {askResult && <AskLegalMindResult result={askResult} />}
    </>
  );

  const renderCompareCasesPage = () => (
    <>
      <PageHeader
        eyebrow="LegalMind AI"
        title="Compare Cases"
        description="Compare indexed judgments or upload your own legal documents for AI-powered comparison."
      />

      {error && (
        <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          <AlertCircle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Indexed case comparison */}
      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-6 flex items-start justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <GitCompare size={20} className="text-blue-700" />
              <h3 className="text-lg font-bold text-slate-900">
                Compare Indexed Cases
              </h3>
            </div>

            <p className="mt-1 text-sm text-slate-500">
              Choose two judgments from the LegalMind AI knowledge base.
            </p>
          </div>

          <button
            type="button"
            onClick={() => loadCompareCases(true)}
            disabled={compareCasesLoading}
            className="inline-flex items-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
          >
            {compareCasesLoading ? (
              <Loader2 size={15} className="animate-spin" />
            ) : (
              <RotateCcw size={15} />
            )}

            {compareCasesLoading ? "Loading Cases..." : "Refresh Cases"}
          </button>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <CaseSelector
            label="Case A"
            value={compareCaseA}
            onChange={setCompareCaseA}
            cases={compareCases}
            onFocus={() => loadCompareCases()}
          />

          <CaseSelector
            label="Case B"
            value={compareCaseB}
            onChange={setCompareCaseB}
            cases={compareCases}
            onFocus={() => loadCompareCases()}
          />
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-xs text-slate-400">
            Comparison uses indexed judgment passages and metadata.
          </p>

          <button
            type="button"
            onClick={compareSelectedCases}
            disabled={compareLoading || !compareCaseA || !compareCaseB}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {compareLoading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Comparing Cases...
              </>
            ) : (
              <>
                <GitCompare size={18} />
                Compare Indexed Cases
              </>
            )}
          </button>
        </div>
      </section>

      {/* Upload your own cases */}
      <section className="mt-6 rounded-2xl border border-blue-100 bg-white p-6 shadow-sm">
        <div className="mb-6">
          <div className="flex items-center gap-2">
            <Upload size={20} className="text-blue-700" />
            <h3 className="text-lg font-bold text-slate-900">
              Compare Your Own PDFs
            </h3>
          </div>

          <p className="mt-1 max-w-2xl text-sm leading-6 text-slate-500">
            Upload two legal PDF documents and LegalMind AI will compare their
            facts, legal issues, arguments, reasoning, decisions, Acts and
            sections.
          </p>
        </div>

        <div className="grid gap-5 lg:grid-cols-2">
          <CompareUploadCard
            label="Case A"
            file={uploadCaseA}
            onChange={(event) => handleComparePdfChange(event, "A")}
            onClear={() => {
              setUploadCaseA(null);
              setUploadCompareResult(null);
            }}
          />

          <CompareUploadCard
            label="Case B"
            file={uploadCaseB}
            onChange={(event) => handleComparePdfChange(event, "B")}
            onClear={() => {
              setUploadCaseB(null);
              setUploadCompareResult(null);
            }}
          />
        </div>

        <div className="mt-6 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold text-slate-600">
              Private document comparison
            </p>
            <p className="mt-1 text-[11px] text-slate-400">
              These PDFs are compared directly and are not added to the
              permanent legal knowledge base.
            </p>
          </div>

          <button
            type="button"
            onClick={compareUploadedCases}
            disabled={uploadCompareLoading || !uploadCaseA || !uploadCaseB}
            className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {uploadCompareLoading ? (
              <>
                <Loader2 size={18} className="animate-spin" />
                Comparing PDFs...
              </>
            ) : (
              <>
                <GitCompare size={18} />
                Compare My PDFs
              </>
            )}
          </button>
        </div>
      </section>

      {compareResult && <CaseComparisonResult result={compareResult} />}

      {uploadCompareResult && (
        <CaseComparisonResult result={uploadCompareResult} />
      )}
    </>
  );

  const renderLegalDocumentsPage = () => {
    const search = documentsSearch.trim().toLowerCase();

    const filteredDocuments = legalDocuments.filter((item) => {
      const matchesSearch =
        !search ||
        [
          item.case_name,
          item.case_number,
          item.citation,
          item.court,
          item.jurisdiction,
          ...(item.acts || []),
          ...(item.sections || []),
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(search);

      const matchesCourt =
        !documentsCourt ||
        (item.court || "")
          .toLowerCase()
          .includes(documentsCourt.toLowerCase());

      const matchesType =
        !documentsType ||
        (item.document_type || "").toLowerCase() ===
          documentsType.toLowerCase();

      return matchesSearch && matchesCourt && matchesType;
    });

    return (
      <>
        <PageHeader
          eyebrow="Knowledge Base"
          title="Legal Documents"
          description="Browse judgments and legal documents indexed inside the LegalMind AI knowledge base."
        />

        {error && activePage === "Legal Documents" && (
          <div className="mb-6 flex items-start gap-3 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
            <AlertCircle size={18} className="mt-0.5 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <div className="mb-6 flex flex-col justify-between gap-4 md:flex-row md:items-center">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
                <Library size={22} />
              </div>

              <div>
                <h3 className="text-lg font-bold text-slate-900">
                  Indexed Legal Knowledge
                </h3>

                <p className="mt-1 text-sm text-slate-500">
                  {documentsLoading
                    ? "Loading documents..."
                    : `${filteredDocuments.length} document${
                        filteredDocuments.length === 1 ? "" : "s"
                      } available`}
                </p>
              </div>
            </div>

            <button
              type="button"
              onClick={() => loadLegalDocuments(true)}
              disabled={documentsLoading}
              className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {documentsLoading ? (
                <Loader2 size={15} className="animate-spin" />
              ) : (
                <RotateCcw size={15} />
              )}

              {documentsLoading ? "Loading..." : "Refresh"}
            </button>
          </div>

          <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-4">
            <div className="relative">
              <Search
                size={18}
                className="pointer-events-none absolute left-4 top-1/2 -translate-y-1/2 text-slate-400"
              />

              <input
                value={documentsSearch}
                onChange={(event) => setDocumentsSearch(event.target.value)}
                placeholder="Search by case name, citation, court, Act or section..."
                className="w-full rounded-xl border border-slate-200 bg-white py-3.5 pl-11 pr-4 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
              />
            </div>

            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <select
                value={documentsCourt}
                onChange={(event) => setDocumentsCourt(event.target.value)}
                className={SELECT_CLASS}
              >
                {COURT_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>

              <select
                value={documentsType}
                onChange={(event) => setDocumentsType(event.target.value)}
                className={SELECT_CLASS}
              >
                {DOCUMENT_TYPE_OPTIONS.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {documentsLoading && (
            <div className="flex min-h-[280px] items-center justify-center">
              <div className="text-center">
                <Loader2
                  size={32}
                  className="mx-auto animate-spin text-blue-700"
                />
                <p className="mt-4 text-sm font-semibold text-slate-700">
                  Loading LegalMind knowledge base...
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  Fetching indexed legal documents
                </p>
              </div>
            </div>
          )}

          {!documentsLoading && filteredDocuments.length === 0 && (
            <div className="mt-6 rounded-2xl border border-dashed border-slate-300 bg-slate-50 px-6 py-16 text-center">
              <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-white text-slate-400 shadow-sm">
                <Library size={25} />
              </div>
              <h4 className="mt-4 text-base font-bold text-slate-800">
                No documents found
              </h4>
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">
                Try changing your search or filters.
              </p>
            </div>
          )}

          {!documentsLoading && filteredDocuments.length > 0 && (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {filteredDocuments.map((item, index) => (
                <LegalDocumentCard
                  key={item.case_key || `${item.case_name}-${index}`}
                  document={item}
                  onClick={() => setSelectedDocument(item)}
                />
              ))}
            </div>
          )}
        </section>
      </>
    );
  };

  const renderPlaceholder = (title, description, icon) => (
    <>
      <PageHeader
        eyebrow="LegalMind AI"
        title={title}
        description={description}
      />

      <section className="flex min-h-[420px] max-w-4xl items-center justify-center rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="text-center">
          <div className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl bg-blue-50 text-blue-700">
            {icon}
          </div>

          <h3 className="text-xl font-bold text-slate-900">{title}</h3>

          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-500">
            This LegalMind AI module is ready for integration. We will connect
            it to the backend in the next development step.
          </p>

          <button
            type="button"
            onClick={() => navigate("Dashboard")}
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white hover:bg-blue-800"
          >
            <ArrowLeft size={16} />
            Back to Dashboard
          </button>
        </div>
      </section>
    </>
  );

  const renderPage = () => {
    switch (activePage) {
      case "Analyze Current Case":
        return renderAnalyzePage();

      case "Case Law Search":
        return renderCaseLawSearchPage();

      case "Ask LegalMind":
        return renderAskLegalMindPage();

      case "Compare Cases":
        return renderCompareCasesPage();

      case "Legal Documents":
        return renderLegalDocumentsPage();

      case "Analytics":
        return renderPlaceholder(
          "Analytics",
          "View LegalMind AI research and knowledge-base analytics.",
          <BarChart3 size={27} />
        );

      case "Settings":
        return renderPlaceholder(
          "Settings",
          "Manage LegalMind AI workspace settings.",
          <Settings size={27} />
        );

      default:
        return renderDashboard();
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <style>{`
        @media print {
          header,
          aside,
          button,
          footer {
            display: none !important;
          }

          main {
            padding-left: 0 !important;
            padding-top: 0 !important;
          }

          body {
            background: white !important;
          }
        }
      `}</style>

      <header className="fixed left-0 right-0 top-0 z-50 h-[72px] border-b border-slate-200 bg-white">
        <div className="flex h-full items-center justify-between px-7">
          <button
            type="button"
            onClick={() => navigate("Dashboard")}
            className="flex items-center gap-3"
          >
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-700 text-white shadow-sm">
              <Scale size={22} strokeWidth={2.2} />
            </div>

            <div className="text-left">
              <h1 className="text-lg font-bold tracking-tight text-slate-900">
                LegalMind AI
              </h1>
              <p className="text-[11px] font-medium text-slate-400">
                Legal Intelligence Platform
              </p>
            </div>
          </button>

          <div className="flex items-center gap-5">
            <button
              type="button"
              className="relative rounded-lg p-2 text-slate-500 hover:bg-slate-100"
            >
              <Bell size={20} />
              <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-blue-600 ring-2 ring-white" />
            </button>

            <div className="h-7 w-px bg-slate-200" />

            <button
              type="button"
              className="flex items-center gap-3 rounded-xl px-2 py-1.5 hover:bg-slate-50"
            >
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-100 text-sm font-bold text-blue-700">
                A
              </div>

              <div className="hidden text-left sm:block">
                <p className="text-sm font-semibold text-slate-800">
                  Legal Researcher
                </p>
                <p className="text-[11px] text-slate-400">
                  Research Workspace
                </p>
              </div>

              <ChevronDown size={16} className="text-slate-400" />
            </button>
          </div>
        </div>
      </header>

      <aside className="fixed bottom-0 left-0 top-[72px] z-40 hidden w-[240px] border-r border-slate-200 bg-white lg:block">
        <div className="flex h-full flex-col">
          <nav className="flex-1 px-4 py-6">
            <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">
              Workspace
            </p>

            <SidebarItem
              icon={<LayoutDashboard size={18} />}
              label="Dashboard"
              active={activePage === "Dashboard"}
              onClick={() => navigate("Dashboard")}
            />

            <SidebarItem
              icon={<Search size={18} />}
              label="Case Law Search"
              active={activePage === "Case Law Search"}
              onClick={() => navigate("Case Law Search")}
            />

            <SidebarItem
              icon={<Scale size={18} />}
              label="Ask LegalMind"
              active={activePage === "Ask LegalMind"}
              onClick={() => navigate("Ask LegalMind")}
            />

            <SidebarItem
              icon={<FileText size={18} />}
              label="Analyze Current Case"
              active={activePage === "Analyze Current Case"}
              onClick={() => navigate("Analyze Current Case")}
            />

            <SidebarItem
              icon={<GitCompare size={18} />}
              label="Compare Cases"
              active={activePage === "Compare Cases"}
              onClick={() => navigate("Compare Cases")}
            />

            <div className="my-6 h-px bg-slate-100" />

            <p className="mb-3 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-slate-400">
              Knowledge
            </p>

            <SidebarItem
              icon={<Library size={18} />}
              label="Legal Documents"
              active={activePage === "Legal Documents"}
              onClick={() => navigate("Legal Documents")}
            />

            <SidebarItem
              icon={<BarChart3 size={18} />}
              label="Analytics"
              active={activePage === "Analytics"}
              onClick={() => navigate("Analytics")}
            />
          </nav>

          <div className="border-t border-slate-100 p-4">
            <SidebarItem
              icon={<Settings size={18} />}
              label="Settings"
              active={activePage === "Settings"}
              onClick={() => navigate("Settings")}
            />

            <div className="mt-4 rounded-xl bg-slate-50 p-4">
              <div className="mb-2 flex items-center gap-2">
                <div className="h-2 w-2 rounded-full bg-emerald-500" />
                <span className="text-xs font-semibold text-slate-700">
                  AI System Online
                </span>
              </div>

              <p className="text-[11px] leading-5 text-slate-400">
                Legal knowledge base and AI services are operational.
              </p>
            </div>
          </div>
        </div>
      </aside>

      <main className="pt-[72px] lg:pl-[240px]">
        <div className="mx-auto max-w-[1500px] px-6 py-8 lg:px-8">
          {renderPage()}

          {selectedDocument && (
            <LegalDocumentDetails
              document={selectedDocument}
              onClose={() => setSelectedDocument(null)}
              onAsk={() => {
                setAskQuestion(
                  `Explain the legal principles and reasoning in ${
                    selectedDocument.case_name || "this case"
                  }.`
                );
                setSelectedDocument(null);
                navigate("Ask LegalMind");
              }}
            />
          )}

          <div className="mt-8 flex flex-col justify-between gap-2 border-t border-slate-200 pt-5 text-xs text-slate-400 sm:flex-row">
            <span>LegalMind AI v1.0.0</span>
            <span>
              AI-powered legal research • Human verification recommended
            </span>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ==================================================================== */
/* Shared components                                                     */
/* ==================================================================== */

function PageHeader({
  eyebrow,
  title,
  description,
  buttonText,
  buttonIcon,
  onButtonClick,
}) {
  return (
    <div className="mb-8 flex flex-col justify-between gap-5 md:flex-row md:items-end">
      <div>
        <p className="mb-2 text-sm font-medium text-blue-600">{eyebrow}</p>
        <h2 className="text-3xl font-bold tracking-tight text-slate-900">
          {title}
        </h2>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          {description}
        </p>
      </div>

      {buttonText && (
        <button
          type="button"
          onClick={onButtonClick}
          className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-blue-800"
        >
          {buttonIcon}
          {buttonText}
        </button>
      )}
    </div>
  );
}

function SidebarItem({ icon, label, active = false, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`mb-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-sm font-medium transition ${
        active
          ? "bg-blue-50 text-blue-700"
          : "text-slate-500 hover:bg-slate-50 hover:text-slate-900"
      }`}
    >
      {icon}
      <span>{label}</span>
    </button>
  );
}

function StatCard({ title, value, subtitle, icon, trend, online = false }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex items-start justify-between">
        <div className="rounded-xl bg-slate-50 p-2.5 text-slate-600">
          {icon}
        </div>

        {online && (
          <span className="flex items-center gap-1.5 text-[11px] font-semibold text-emerald-600">
            <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
            Live
          </span>
        )}
      </div>

      <p className="mt-5 text-xs font-medium text-slate-400">{title}</p>

      <p className="mt-1 text-2xl font-bold tracking-tight text-slate-900">
        {value}
      </p>

      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-xs text-slate-400">{subtitle}</span>
        <span className="text-[10px] font-semibold text-blue-600">{trend}</span>
      </div>
    </div>
  );
}

function ResearchCard({ icon, title, description, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group rounded-xl border border-slate-200 p-4 text-left transition hover:-translate-y-0.5 hover:border-blue-200 hover:bg-blue-50/40 hover:shadow-sm"
    >
      <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-xl bg-slate-100 text-slate-600 group-hover:bg-blue-100 group-hover:text-blue-700">
        {icon}
      </div>

      <h4 className="text-sm font-bold text-slate-800">{title}</h4>

      <p className="mt-1.5 text-xs leading-5 text-slate-500">{description}</p>

      <span className="mt-4 inline-block text-xs font-semibold text-blue-700">
        Open →
      </span>
    </button>
  );
}

function ActivityItem({ title, description, time, icon }) {
  return (
    <div className="flex items-center gap-3 rounded-xl px-2 py-3">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-slate-500">
        {icon}
      </div>

      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-slate-800">{title}</p>
        <p className="mt-0.5 truncate text-xs text-slate-400">{description}</p>
      </div>

      <span className="shrink-0 text-[11px] text-slate-400">{time}</span>
    </div>
  );
}

function KnowledgeCard({ court, cases, type }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
      <div className="flex items-center justify-between">
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-white text-blue-700 shadow-sm">
          <Scale size={17} />
        </div>

        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
          {type}
        </span>
      </div>

      <h4 className="mt-4 text-sm font-bold text-slate-800">{court}</h4>

      <p className="mt-1 text-xs text-slate-500">{cases} indexed cases</p>
    </div>
  );
}

function InfoItem({ label, value }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        {label}
      </p>

      <p className="mt-1 break-words text-xs font-semibold text-slate-700">
        {value}
      </p>
    </div>
  );
}

function TagSection({ title, items, blue = false }) {
  return (
    <div className="mt-4">
      <p className="text-xs font-bold text-slate-700">{title}</p>

      <div className="mt-2 flex flex-wrap gap-2">
        {items.map((item, index) => (
          <span
            key={index}
            className={
              blue
                ? "rounded-full bg-blue-50 px-3 py-1 text-[11px] font-medium text-blue-700"
                : "rounded-full bg-slate-100 px-3 py-1 text-[11px] font-medium text-slate-600"
            }
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function ResearchMetric({ label, value, description }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>
      <p className="mt-1 text-lg font-bold text-slate-900">{value}</p>
      <p className="mt-0.5 text-[11px] text-slate-400">{description}</p>
    </div>
  );
}

function formatLabel(value) {
  return String(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function openJudgmentPdf(sourceFile, pageNumber = null) {
  if (!sourceFile) return;

  // Metadata may contain a full Windows path or just the PDF filename.
  // The backend safely reduces it to the actual filename.
  const filename = String(sourceFile).split(/[\\/]/).pop();

  if (!filename) return;

  const page =
    pageNumber !== null && pageNumber !== undefined && Number(pageNumber) > 0
      ? `#page=${Number(pageNumber)}`
      : "";

  const pdfUrl = `/api/documents/${encodeURIComponent(filename)}${page}`;

  window.open(pdfUrl, "_blank", "noopener,noreferrer");
}

/* ==================================================================== */
/* Legal documents                                                       */
/* ==================================================================== */

function DocumentDetail({ label, value }) {
  return (
    <div className="rounded-xl border border-slate-100 bg-slate-50 p-4">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
        {label}
      </p>

      <p className="mt-1 text-sm font-semibold leading-5 text-slate-800">
        {value || "Not available"}
      </p>
    </div>
  );
}

function LegalDocumentDetails({ document, onClose, onAsk }) {
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/40 p-4 backdrop-blur-sm">
      <div className="max-h-[90vh] w-full max-w-3xl overflow-y-auto rounded-2xl border border-slate-200 bg-white shadow-2xl">
        <div className="sticky top-0 flex items-start justify-between border-b border-slate-100 bg-white p-6">
          <div className="flex min-w-0 items-start gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
              <FileText size={23} />
            </div>

            <div className="min-w-0">
              <p className="text-xs font-bold uppercase tracking-wider text-blue-600">
                Legal Document
              </p>

              <h3 className="mt-1 text-lg font-bold leading-6 text-slate-900">
                {document.case_name || "Untitled Case"}
              </h3>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="rounded-lg p-2 text-slate-400 transition hover:bg-slate-100 hover:text-slate-700"
          >
            <X size={19} />
          </button>
        </div>

        <div className="p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <DocumentDetail label="Court" value={document.court} />
            <DocumentDetail
              label="Judgment Date"
              value={document.judgment_date}
            />
            <DocumentDetail label="Case Number" value={document.case_number} />
            <DocumentDetail label="Citation" value={document.citation} />
            <DocumentDetail
              label="Document Type"
              value={document.document_type}
            />
            <DocumentDetail
              label="Jurisdiction"
              value={document.jurisdiction}
            />
          </div>

          {document.acts?.length > 0 && (
            <div className="mt-6">
              <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                Acts
              </p>

              <div className="flex flex-wrap gap-2">
                {document.acts.map((act, index) => (
                  <span
                    key={index}
                    className="rounded-lg bg-blue-50 px-3 py-2 text-xs font-semibold text-blue-700"
                  >
                    {act}
                  </span>
                ))}
              </div>
            </div>
          )}

          {document.sections?.length > 0 && (
            <div className="mt-5">
              <p className="mb-2 text-xs font-bold uppercase tracking-wider text-slate-500">
                Sections
              </p>

              <div className="flex flex-wrap gap-2">
                {document.sections.map((section, index) => (
                  <span
                    key={index}
                    className="rounded-lg bg-slate-100 px-3 py-2 text-xs font-semibold text-slate-700"
                  >
                    {section}
                  </span>
                ))}
              </div>
            </div>
          )}

          {document.source_url && (
            <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Source
              </p>

              <p className="mt-2 break-all text-xs leading-5 text-slate-500">
                {document.source_url}
              </p>
            </div>
          )}

          <div className="mt-6 flex flex-col gap-3 border-t border-slate-100 pt-5 sm:flex-row sm:justify-end">
            <button
              type="button"
              onClick={onClose}
              className="rounded-xl border border-slate-200 px-5 py-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            >
              Close
            </button>

            <button
              type="button"
              onClick={onAsk}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-blue-700 px-5 py-3 text-sm font-semibold text-white transition hover:bg-blue-800"
            >
              <Scale size={17} />
              Ask LegalMind About This Case
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function LegalDocumentCard({ document, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group w-full rounded-2xl border border-slate-200 bg-white p-5 text-left transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md"
    >
      <div className="flex items-start gap-4">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
          <FileText size={21} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <h4 className="line-clamp-2 text-sm font-bold leading-5 text-slate-900 group-hover:text-blue-700">
              {document.case_name || "Untitled Case"}
            </h4>

            <ArrowUpRight
              size={17}
              className="shrink-0 text-slate-300 transition group-hover:text-blue-600"
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            {document.court && (
              <span className="rounded-md bg-slate-100 px-2 py-1 text-[10px] font-semibold text-slate-600">
                {document.court}
              </span>
            )}

            {document.document_type && (
              <span className="rounded-md bg-blue-50 px-2 py-1 text-[10px] font-semibold capitalize text-blue-700">
                {document.document_type}
              </span>
            )}
          </div>

          <div className="mt-4 space-y-1.5">
            {document.judgment_date && (
              <p className="text-xs text-slate-500">
                <span className="font-semibold text-slate-600">Judgment:</span>{" "}
                {document.judgment_date}
              </p>
            )}

            {document.citation && (
              <p className="truncate text-xs text-slate-500">
                <span className="font-semibold text-slate-600">Citation:</span>{" "}
                {document.citation}
              </p>
            )}

            {document.case_number && (
              <p className="truncate text-xs text-slate-500">
                <span className="font-semibold text-slate-600">Case No:</span>{" "}
                {document.case_number}
              </p>
            )}
          </div>
        </div>
      </div>
    </button>
  );
}

/* ==================================================================== */
/* Case law search results                                               */
/* ==================================================================== */

function CaseLawSearchResults({ result }) {
  const results = result.results || [];

  return (
    <section className="mt-6 max-w-6xl">
      <div className="mb-4 flex flex-col justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-5 shadow-sm sm:flex-row sm:items-center">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-blue-600">
            Research Results
          </p>
          <h3 className="mt-1 text-xl font-bold tracking-tight text-slate-900">
            {result.total_results || 0} Relevant Judgment
            {(result.total_results || 0) === 1 ? "" : "s"}
          </h3>
          <p className="mt-1 max-w-3xl text-sm text-slate-500">
            Results for:{" "}
            <span className="font-semibold text-slate-700">
              {result.question || "Legal search"}
            </span>
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-100 bg-emerald-50 px-3 py-1.5 text-[11px] font-bold text-emerald-700">
            <CheckCircle2 size={14} />
            Hybrid Search
          </span>
          <span className="rounded-full bg-slate-100 px-3 py-1.5 text-[11px] font-semibold text-slate-500">
            {results.length} displayed
          </span>
        </div>
      </div>

      {results.length === 0 ? (
        <div className="rounded-2xl border border-slate-200 bg-white p-12 text-center shadow-sm">
          <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            <Search size={28} />
          </div>
          <h4 className="mt-4 text-base font-bold text-slate-800">
            No matching judgments found
          </h4>
          <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-slate-400">
            Try a broader legal question, remove a filter, or search using an
            Act, section, legal doctrine, or case topic.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {results.map((item, index) => (
            <CaseLawResultCard
              key={`${item.case_name || "case"}-${item.case_number || ""}-${index}`}
              item={item}
              index={index}
            />
          ))}
        </div>
      )}

      {results.length > 0 && (
        <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
          <strong>Research note:</strong> Relevance scores indicate retrieval
          similarity, not legal correctness, binding precedent, or likelihood of
          a particular outcome. Verify the original judgment and current law
          before relying on it.
        </div>
      )}
    </section>
  );
}

function CaseLawResultCard({ item, index }) {
  const score = Number(item.score || 0);
  const scorePercent = Math.max(0, Math.min(100, score * 100));
  const sourceName = item.source_file
    ? String(item.source_file).split(/[\\/]/).pop()
    : "";

  return (
    <article className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition hover:-translate-y-0.5 hover:border-blue-200 hover:shadow-md">
      <div className="p-5 sm:p-6">
        <div className="flex flex-col justify-between gap-4 lg:flex-row">
          <div className="flex min-w-0 gap-4">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700">
              {index + 1}
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-blue-50 px-2.5 py-1 text-[10px] font-bold uppercase tracking-wider text-blue-700">
                  Judgment Match
                </span>
                {item.document_type && (
                  <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-semibold capitalize text-slate-500">
                    {item.document_type}
                  </span>
                )}
              </div>

              <h4 className="mt-2 text-base font-bold leading-6 text-slate-900">
                {item.case_name || "Case name unavailable"}
              </h4>

              <div className="mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                <span className="font-medium text-slate-700">
                  {item.court || "Court unavailable"}
                </span>

                {item.judgment_date && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span>{item.judgment_date}</span>
                  </>
                )}

                {item.citation && (
                  <>
                    <span className="text-slate-300">•</span>
                    <span>{item.citation}</span>
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="w-full shrink-0 rounded-xl border border-blue-100 bg-blue-50/50 px-4 py-3 lg:w-[145px] lg:text-right">
            <div className="flex items-center justify-between lg:block">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Relevance
              </p>
              <p className="text-lg font-bold text-blue-700">
                {scorePercent.toFixed(1)}%
              </p>
            </div>
            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-blue-100">
              <div
                className="h-full rounded-full bg-blue-600"
                style={{ width: `${scorePercent}%` }}
              />
            </div>
          </div>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <InfoItem
            label="Case Number"
            value={item.case_number || "Not available"}
          />
          <InfoItem
            label="Judgment Date"
            value={item.judgment_date || "Not available"}
          />
          <InfoItem
            label="Document Type"
            value={item.document_type || "Not available"}
          />
          <InfoItem label="Page" value={item.page_number ?? "Not available"} />
        </div>

        {item.acts?.length > 0 && <TagSection title="Acts" items={item.acts} />}

        {item.sections?.length > 0 && (
          <TagSection title="Sections" items={item.sections} blue />
        )}

        {item.text && (
          <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
            <div className="mb-2 flex items-center gap-2">
              <BookOpen size={15} className="text-blue-600" />
              <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
                Relevant Passage
              </p>
            </div>

            <p className="text-sm leading-6 text-slate-600">{item.text}</p>
          </div>
        )}

        <div className="mt-5 flex flex-col gap-3 border-t border-slate-100 pt-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
              Source Document
            </p>
            <p className="mt-1 truncate text-xs font-medium text-slate-600">
              {sourceName || "PDF reference unavailable"}
            </p>
          </div>

          <button
            type="button"
            onClick={() => openJudgmentPdf(item.source_file, item.page_number)}
            disabled={!item.source_file}
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-xs font-semibold text-white shadow-sm transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <ExternalLink size={15} />
            Open Judgment PDF
          </button>
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
          {item.jurisdiction && (
            <span className="rounded-full bg-slate-100 px-3 py-1">
              Jurisdiction: {item.jurisdiction}
            </span>
          )}
          {sourceName && (
            <span className="max-w-full truncate rounded-full bg-slate-100 px-3 py-1">
              Indexed source: {sourceName}
            </span>
          )}
        </div>
      </div>
    </article>
  );
}

/* ==================================================================== */
/* Ask LegalMind result                                                  */
/* ==================================================================== */

function AskLegalMindResult({ result }) {
  const sources = result.sources || [];
  const answer = result.answer || "No grounded answer was returned.";
  const question = result.question || result.query || "";

  const [translationLanguage, setTranslationLanguage] = useState("English");
  const [translatedAnswer, setTranslatedAnswer] = useState("");
  const [translationLoading, setTranslationLoading] = useState(false);
  const [translationError, setTranslationError] = useState("");

  const copyAnswer = async () => {
    try {
      await navigator.clipboard.writeText(answer);
    } catch {
      // Clipboard may be unavailable
    }
  };

  const printAnswer = () => {
    window.print();
  };

  const handleTranslate = async (language) => {
    setTranslationLanguage(language);
    setTranslationError("");

    if (language === "English") {
      setTranslatedAnswer("");
      setTranslationLoading(false);
      return;
    }

    setTranslationLoading(true);
    setTranslatedAnswer("");

    try {
      const response = await fetch("/api/translate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: answer,
          target_language: language,
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Translation failed.");
      }

      setTranslatedAnswer(data.translated_text || "");
    } catch (requestError) {
      setTranslationError(
        requestError.message || "Could not translate the answer."
      );
    } finally {
      setTranslationLoading(false);
    }
  };

  return (
    <section className="mt-6 max-w-6xl space-y-5">
      <div className="rounded-2xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-100 p-6">
          <div className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div className="flex items-start gap-3">
              <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
                <CheckCircle2 size={22} />
              </div>

              <div className="min-w-0">
                <h3 className="text-lg font-bold text-slate-900">
                  LegalMind Research Answer
                </h3>
                <p className="mt-1 text-xs text-slate-400">
                  Grounded in retrieved documents from the LegalMind AI
                  knowledge base
                </p>
              </div>
            </div>

            <div className="flex shrink-0 items-center gap-2">
              <button
                type="button"
                onClick={copyAnswer}
                className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-600 transition hover:bg-slate-50"
              >
                Copy Answer
              </button>

              <button
                type="button"
                onClick={printAnswer}
                className="rounded-lg bg-blue-700 px-3 py-2 text-xs font-semibold text-white transition hover:bg-blue-800"
              >
                Print Report
              </button>
            </div>
          </div>

          {question && (
            <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">
                Research Question
              </p>
              <p className="mt-1 text-sm font-medium leading-6 text-slate-700">
                {question}
              </p>
            </div>
          )}
        </div>

        <div className="p-6">
          <div className="mb-4 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <BookOpen size={17} className="text-blue-700" />
              <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                AI-Grounded Answer
              </p>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-slate-500">
                Translate
              </span>

              <div className="relative">
                <select
                  value={translationLanguage}
                  onChange={(event) => handleTranslate(event.target.value)}
                  disabled={translationLoading}
                  className="appearance-none rounded-lg border border-slate-200 bg-white py-2 pl-3 pr-8 text-xs font-semibold text-slate-700 outline-none transition hover:border-blue-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-100 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {LANGUAGE_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>

                <ChevronDown
                  size={14}
                  className="pointer-events-none absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400"
                />
              </div>
            </div>
          </div>

          {translationLanguage === "English" && (
            <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-5">
              <div className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                {answer}
              </div>
            </div>
          )}

          {translationLoading && (
            <div className="flex items-center gap-3 rounded-2xl border border-blue-100 bg-blue-50/40 p-5">
              <Loader2 size={18} className="animate-spin text-blue-700" />
              <div>
                <p className="text-sm font-semibold text-slate-800">
                  Translating legal answer...
                </p>
                <p className="mt-0.5 text-xs text-slate-400">
                  Preserving legal meaning and terminology
                </p>
              </div>
            </div>
          )}

          {translationError && !translationLoading && (
            <div className="flex items-start gap-3 rounded-2xl border border-red-200 bg-red-50 p-5">
              <AlertCircle
                size={18}
                className="mt-0.5 shrink-0 text-red-600"
              />
              <div>
                <p className="text-sm font-semibold text-red-800">
                  Translation failed
                </p>
                <p className="mt-1 text-xs leading-5 text-red-700">
                  {translationError}
                </p>
              </div>
            </div>
          )}

          {translationLanguage !== "English" &&
            translatedAnswer &&
            !translationLoading && (
              <div className="rounded-2xl border border-blue-100 bg-blue-50/40 p-5">
                <div className="mb-4 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <BookOpen size={16} className="text-blue-700" />
                    <p className="text-xs font-bold uppercase tracking-wider text-blue-700">
                      {translationLanguage} Translation
                    </p>
                  </div>

                  <span className="rounded-full bg-blue-100 px-2.5 py-1 text-[10px] font-semibold text-blue-700">
                    AI Translated
                  </span>
                </div>

                <div className="rounded-xl border border-white bg-white p-5">
                  <div className="whitespace-pre-wrap text-sm leading-7 text-slate-700">
                    {translatedAnswer}
                  </div>
                </div>

                <p className="mt-3 text-[10px] leading-5 text-slate-400">
                  Translation is provided for research convenience. Verify
                  important legal terminology against the original English
                  answer and authoritative sources.
                </p>
              </div>
            )}

          <div className="mt-5 grid gap-3 sm:grid-cols-3">
            <ResearchMetric
              label="Sources Used"
              value={sources.length}
              description="Retrieved legal sources"
            />
            <ResearchMetric
              label="Research Mode"
              value="Grounded"
              description="Retrieval-backed answer"
            />
            <ResearchMetric
              label="Verification"
              value="Required"
              description="Human legal verification"
            />
          </div>

          <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <div className="flex gap-3">
              <AlertCircle
                size={17}
                className="mt-0.5 shrink-0 text-amber-600"
              />
              <div>
                <p className="text-xs font-bold text-amber-800">
                  Legal Research Disclaimer
                </p>
                <p className="mt-1 text-xs leading-5 text-amber-800">
                  LegalMind AI is a legal research assistant, not a substitute
                  for professional legal advice. Verify cited judgments, current
                  law, amendments, and jurisdiction with authoritative legal
                  sources.
                </p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
          <div>
            <div className="flex items-center gap-2">
              <FileText size={19} className="text-blue-700" />
              <h3 className="text-lg font-bold text-slate-900">
                Retrieved Legal Sources
              </h3>
            </div>

            <p className="mt-1 text-sm text-slate-500">
              Source passages used to ground the AI-generated research answer.
            </p>
          </div>

          <span className="w-fit rounded-full bg-blue-50 px-3 py-1.5 text-xs font-bold text-blue-700">
            {sources.length} source{sources.length === 1 ? "" : "s"}
          </span>
        </div>

        {sources.length === 0 ? (
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
            <FileText size={28} className="mx-auto text-slate-400" />
            <p className="mt-3 text-sm font-semibold text-slate-700">
              No source records were returned.
            </p>
            <p className="mt-1 text-xs text-slate-400">
              Try a more specific legal question.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {sources.map((source, index) => (
              <AskSourceCard
                key={`${source.case_name || "source"}-${index}`}
                source={source}
                index={index}
              />
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

function AskSourceCard({ source, index }) {
  return (
    <article className="rounded-xl border border-slate-200 p-5 transition hover:border-blue-200 hover:shadow-sm">
      <div className="flex flex-col justify-between gap-4 lg:flex-row">
        <div className="flex min-w-0 gap-4">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-xs font-bold text-blue-700">
            {index + 1}
          </div>
          <div className="min-w-0">
            <h4 className="text-sm font-bold leading-6 text-slate-900">
              {source.case_name || "Case name unavailable"}
            </h4>
            <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
              <span>{source.court || "Court unavailable"}</span>
              {source.judgment_date && <span>• {source.judgment_date}</span>}
              {source.citation && <span>• {source.citation}</span>}
            </div>
          </div>
        </div>

        {source.reranker_score !== undefined &&
          source.reranker_score !== null && (
            <div className="rounded-lg bg-slate-50 px-3 py-2 lg:text-right">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                Reranker Score
              </p>
              <p className="mt-0.5 text-sm font-bold text-blue-700">
                {Number(source.reranker_score).toFixed(3)}
              </p>
            </div>
          )}
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <InfoItem
          label="Case Number"
          value={source.case_number || "Not available"}
        />
        <InfoItem
          label="Document Type"
          value={source.document_type || "Not available"}
        />
        <InfoItem label="Page" value={source.page_number ?? "Not available"} />
        <InfoItem
          label="Citation"
          value={source.citation || "Not available"}
        />
      </div>

      {source.source_file && (
        <div className="mt-4 flex flex-col gap-3 rounded-xl border border-blue-100 bg-blue-50/40 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 items-center gap-3">
            <FileText size={18} className="shrink-0 text-blue-700" />
            <p className="truncate text-xs font-medium text-slate-600">
              {String(source.source_file).split(/[\\/]/).pop()}
            </p>
          </div>
          <button
            type="button"
            onClick={() =>
              openJudgmentPdf(source.source_file, source.page_number)
            }
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-blue-700 px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-blue-800"
          >
            <FileText size={15} />
            Open Judgment PDF
          </button>
        </div>
      )}
    </article>
  );
}

/* ==================================================================== */
/* Compare                                                               */
/* ==================================================================== */

function CompareUploadCard({ label, file, onChange, onClear }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-slate-50/60 p-5">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wider text-slate-500">
            {label}
          </p>
          <p className="mt-1 text-sm font-semibold text-slate-800">
            Legal PDF Document
          </p>
        </div>

        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-100 text-blue-700">
          <FileText size={19} />
        </div>
      </div>

      {!file ? (
        <label className="group flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-white px-5 py-10 text-center transition hover:border-blue-400 hover:bg-blue-50/30">
          <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-blue-50 text-blue-700">
            <Upload size={21} />
          </div>

          <p className="text-sm font-bold text-slate-700">Upload {label}</p>
          <p className="mt-1 text-xs text-slate-400">PDF files only</p>

          <span className="mt-4 rounded-lg bg-blue-700 px-4 py-2 text-xs font-semibold text-white">
            Choose PDF
          </span>

          <input
            type="file"
            accept=".pdf,application/pdf"
            className="hidden"
            onChange={onChange}
          />
        </label>
      ) : (
        <div className="rounded-xl border border-blue-100 bg-blue-50/50 p-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-blue-700 shadow-sm">
              <FileText size={19} />
            </div>

            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-bold text-slate-800">
                {file.name}
              </p>
              <p className="mt-1 text-xs text-slate-400">
                {(file.size / 1024 / 1024).toFixed(2)} MB
              </p>
            </div>

            <button
              type="button"
              onClick={onClear}
              className="rounded-lg p-2 text-slate-400 transition hover:bg-white hover:text-red-500"
            >
              <X size={17} />
            </button>
          </div>

          <div className="mt-3 flex items-center gap-2 text-xs text-emerald-600">
            <CheckCircle2 size={14} />
            PDF ready for comparison
          </div>
        </div>
      )}
    </div>
  );
}

function CaseSelector({ label, value, onChange, cases, onFocus }) {
  return (
    <div>
      <label className="mb-2 block text-xs font-bold uppercase tracking-wider text-slate-500">
        {label}
      </label>
      <select
        value={value}
        onFocus={onFocus}
        onChange={(event) => onChange(event.target.value)}
        className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm text-slate-700 outline-none transition focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
      >
        <option value="">Select a judgment...</option>
        {cases.map((item, index) => {
          const valueKey =
            item.case_key ||
            `${item.case_name || "case"}|||${item.case_number || ""}|||${
              item.judgment_date || ""
            }|||${item.citation || ""}`;

          return (
            <option key={`${valueKey}-${index}`} value={valueKey}>
              {item.case_name || "Unnamed case"}
              {item.court ? ` — ${item.court}` : ""}
            </option>
          );
        })}
      </select>
      {value && (
        <p className="mt-2 text-xs text-slate-400">
          Selected judgment will be compared using its indexed passages.
        </p>
      )}
    </div>
  );
}

function CaseComparisonResult({ result }) {
  const comparison =
    result?.result?.comparison ||
    result?.comparison ||
    result?.result ||
    result ||
    {};

  const sections = [
    ["Case Information", comparison.case_information],
    ["Facts", comparison.facts],
    ["Legal Issues", comparison.legal_issues],
    ["Arguments", comparison.arguments],
    ["Court's Reasoning", comparison.court_reasoning],
    ["Decision", comparison.decision],
    ["Acts & Sections", comparison.acts_sections],
    ["Similarities", comparison.similarities],
    ["Differences", comparison.differences],
    ["Important Observation", comparison.important_observation],
  ];

  return (
    <section className="mt-6 space-y-6">
      <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-6">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-white text-blue-700 shadow-sm">
            <GitCompare size={19} />
          </div>
          <div>
            <h3 className="text-lg font-bold text-slate-900">
              Case Comparison
            </h3>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              {result?.message ||
                "The comparison below summarizes differences and similarities found in the indexed judgments."}
            </p>
          </div>
        </div>
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        {sections.map(([title, content]) => (
          <ComparisonSection key={title} title={title} content={content} />
        ))}
      </div>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
        <strong>Research note:</strong> Similarity or difference identified by
        LegalMind AI does not by itself establish that one judgment is binding
        precedent or that a particular legal outcome will follow.
      </div>
    </section>
  );
}

function ComparisonSection({ title, content }) {
  if (content === undefined || content === null || content === "") {
    return null;
  }

  const renderContent = (value) => {
    if (Array.isArray(value)) {
      return (
        <ul className="space-y-2">
          {value.map((item, index) => (
            <li
              key={index}
              className="flex gap-2 text-sm leading-6 text-slate-600"
            >
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500" />
              <span>
                {typeof item === "object" ? JSON.stringify(item) : String(item)}
              </span>
            </li>
          ))}
        </ul>
      );
    }

    if (typeof value === "object") {
      return (
        <div className="space-y-3">
          {Object.entries(value).map(([key, item]) => (
            <div key={key}>
              <p className="text-xs font-bold uppercase tracking-wider text-slate-400">
                {formatLabel(key)}
              </p>
              <div className="mt-1 text-sm leading-6 text-slate-600">
                {renderContent(item)}
              </div>
            </div>
          ))}
        </div>
      );
    }

    return (
      <p className="whitespace-pre-wrap text-sm leading-6 text-slate-600">
        {String(value)}
      </p>
    );
  };

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <h4 className="mb-4 text-base font-bold text-slate-900">{title}</h4>
      {renderContent(content)}
    </article>
  );
}

/* ==================================================================== */
/* Case analysis + similar judgments                                     */
/* ==================================================================== */

function CaseAnalysisResult({ result }) {
  const analysis = result.analysis || {};

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-start gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-emerald-50 text-emerald-600">
          <CheckCircle2 size={21} />
        </div>

        <div>
          <h3 className="text-lg font-bold text-slate-900">
            Case Analysis Complete
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            {result.filename} • {result.total_pages} pages processed
          </p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <AnalysisCard title="Legal Issues" items={analysis.legal_issues} />
        <AnalysisCard title="Acts" items={analysis.acts} />
        <AnalysisCard title="Sections" items={analysis.sections} />
        <AnalysisCard title="Legal Concepts" items={analysis.legal_concepts} />
        <AnalysisCard title="Facts" items={analysis.facts} />
        <AnalysisCard title="Arguments" items={analysis.arguments} />
      </div>
    </section>
  );
}

function AnalysisCard({ title, items }) {
  const list = Array.isArray(items) ? items : [];

  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-5">
      <h4 className="text-sm font-bold text-slate-800">{title}</h4>

      {list.length === 0 ? (
        <p className="mt-3 text-xs text-slate-400">
          No information clearly identified.
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {list.map((item, index) => (
            <li
              key={index}
              className="flex gap-2 text-xs leading-5 text-slate-600"
            >
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-blue-600" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function SimilarJudgmentsResult({ result }) {
  const judgments = result.similar_judgments || [];

  return (
    <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-bold text-slate-900">
            Similar Judgments
          </h3>

          <p className="mt-1 text-sm text-slate-500">
            {result.total_similar_cases || 0} relevant judgments found in the
            LegalMind AI knowledge base.
          </p>
        </div>

        <div className="rounded-xl bg-blue-50 px-3 py-2 text-xs font-bold text-blue-700">
          AI Ranked
        </div>
      </div>

      {judgments.length === 0 ? (
        <div className="rounded-xl border border-slate-200 bg-slate-50 p-8 text-center">
          <Scale size={28} className="mx-auto text-slate-400" />

          <p className="mt-3 text-sm font-semibold text-slate-700">
            No similar judgments found.
          </p>

          <p className="mt-1 text-xs text-slate-400">
            Try uploading a case with more identifiable legal content.
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {judgments.map((judgment, index) => (
            <div
              key={index}
              className="rounded-xl border border-slate-200 p-5 transition hover:border-blue-200 hover:shadow-sm"
            >
              <div className="flex flex-col justify-between gap-4 md:flex-row">
                <div className="flex gap-4">
                  <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-blue-50 text-sm font-bold text-blue-700">
                    {index + 1}
                  </div>

                  <div>
                    <h4 className="text-sm font-bold text-slate-900">
                      {judgment.case_name || "Case name unavailable"}
                    </h4>

                    <p className="mt-1 text-xs text-slate-500">
                      {judgment.court || "Court unavailable"}
                    </p>
                  </div>
                </div>

                <div className="rounded-lg bg-slate-50 px-3 py-2 text-right">
                  <p className="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    Relevance
                  </p>

                  <p className="mt-0.5 text-sm font-bold text-blue-700">
                    {Number(judgment.relevance_score || 0).toFixed(3)}
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <InfoItem
                  label="Judgment Date"
                  value={judgment.judgment_date || "Not available"}
                />

                <InfoItem
                  label="Citation"
                  value={judgment.citation || "Not available"}
                />

                <InfoItem
                  label="Document Type"
                  value={judgment.document_type || "Not available"}
                />

                <InfoItem
                  label="Relevant Pages"
                  value={
                    judgment.relevant_pages?.length
                      ? judgment.relevant_pages.join(", ")
                      : "Not available"
                  }
                />
              </div>

              {judgment.acts?.length > 0 && (
                <TagSection title="Acts" items={judgment.acts} blue={false} />
              )}

              {judgment.sections?.length > 0 && (
                <TagSection title="Sections" items={judgment.sections} blue />
              )}
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export default App;
