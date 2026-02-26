import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import JournalDetail from "../JournalDetail.jsx";
import { fetchJournalSignal } from "../api/journal.js";

export default function JournalDetailPage() {
  const { signalId } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!signalId) return;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJournalSignal(signalId);
        setRecord(data);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load journal signal");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [signalId]);

  return (
    <section className="card">
      <h2>Journal Detail</h2>
      {error ? <div className="error">{error}</div> : null}
      {loading ? <p className="muted">Loading...</p> : null}
      {record ? <JournalDetail record={record} onClose={() => navigate("/journal")} /> : null}
    </section>
  );
}
