// App.jsx
import React, { useState, useRef, useEffect } from "react";

export default function App() {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const transcriptRef = useRef();

  async function upload() {
    if (!file) return alert("Choose an audio file first");
    setLoading(true);
    setResult(null);

    const fd = new FormData();
    fd.append("file", file);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: fd,
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || "Upload failed");
      }

      const data = await res.json();
      setResult(data);

      // Scroll transcript to bottom
      setTimeout(() => {
        transcriptRef.current?.scrollIntoView({ behavior: "smooth" });
      }, 100);
    } catch (e) {
      alert("Error: " + e.message);
    } finally {
      setLoading(false);
    }
  }

  // Auto scroll transcript
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [result]);

  return (
    <div
      style={{
        padding: 20,
        fontFamily: "Arial, sans-serif",
        maxWidth: 900,
        margin: "0 auto",
      }}
    >
      <h1 style={{ textAlign: "center" }}>🎙️ Meeting Summarizer</h1>
      <p>
        Upload an audio file (.mp3/.wav) to see transcription and Google AI
        summary.
      </p>

      <div style={{ marginBottom: 10 }}>
        <input
          type="file"
          accept="audio/*"
          onChange={(e) => setFile(e.target.files[0])}
        />
        <button
          onClick={upload}
          disabled={!file || loading}
          style={{ marginLeft: 10, padding: "6px 12px", fontWeight: "bold" }}
        >
          {loading ? "Processing..." : "Upload & Summarize"}
        </button>
      </div>

      {result && (
        <div
          style={{
            display: "flex",
            gap: 20,
            flexDirection: "column",
            marginTop: 20,
          }}
        >
          {/* Summary Card */}
          <div
            style={{
              border: "1px solid #ddd",
              borderRadius: 8,
              padding: 15,
              backgroundColor: "#fefefe",
              boxShadow: "0 2px 5px rgba(0,0,0,0.1)",
            }}
          >
            <h2 style={{ marginTop: 0 }}>📄 Summary</h2>
            <p>{result.summary}</p>
          </div>

          {/* Decisions */}
          <div style={{ borderLeft: "4px solid #4caf50", padding: 10 }}>
            <h3>Decisions</h3>
            {result.decisions.length > 0 ? (
              <ul>
                {result.decisions.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            ) : (
              <p>No decisions extracted.</p>
            )}
          </div>

          {/* Action Items */}
          <div style={{ borderLeft: "4px solid #ff9800", padding: 10 }}>
            <h3>Action Items</h3>
            {result.action_items.length > 0 ? (
              <ul>
                {result.action_items.map((a, i) => (
                  <li key={i}>
                    <strong>{a.text}</strong>
                    {a.owner && <span> — Owner: {a.owner}</span>}
                    {a.due && <span> — Due: {a.due}</span>}
                  </li>
                ))}
              </ul>
            ) : (
              <p>No action items extracted.</p>
            )}
          </div>

          {/* Transcript */}
          <div
            style={{
              border: "1px solid #ddd",
              borderRadius: 8,
              height: 400,
              overflowY: "auto",
              padding: 15,
              backgroundColor: "#f9f9f9",
              whiteSpace: "pre-wrap",
              fontFamily: "monospace",
            }}
            ref={transcriptRef}
          >
            {result.transcript}
          </div>
        </div>
      )}
    </div>
  );
}
