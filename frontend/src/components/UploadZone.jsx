import { useRef, useState } from "react";
import { FileText, UploadCloud, X } from "lucide-react";
import { fileSize } from "../services/format";

export function UploadZone({
  files,
  onChange,
  maxBytes = 10485760,
  disabled = false,
}) {
  const input = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState("");
  function addFiles(incoming) {
    setError("");
    const valid = [];
    for (const file of incoming) {
      if (!/\.(txt|pdf|docx|csv)$/i.test(file.name)) {
        setError("Only TXT, PDF, DOCX and CSV transcripts are supported.");
        continue;
      }
      if (file.size > maxBytes) {
        setError(`${file.name} exceeds the ${fileSize(maxBytes)} limit.`);
        continue;
      }
      if (
        ![...files, ...valid].some(
          (old) => old.name === file.name && old.size === file.size,
        )
      )
        valid.push(file);
    }
    if (files.length + valid.length > 10) {
      setError("Upload at most 10 documents at a time.");
      return;
    }
    onChange([...files, ...valid]);
  }
  return (
    <div>
      <input
        ref={input}
        className="visually-hidden"
        type="file"
        multiple
        accept=".txt,.pdf,.docx,.csv"
        disabled={disabled}
        aria-label="Choose transcript files"
        onChange={(event) => {
          addFiles([...event.target.files]);
          event.target.value = "";
        }}
      />
      <button
        type="button"
        className={`upload-zone ${dragging ? "dragging" : ""}`}
        disabled={disabled}
        onClick={() => input.current.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDragging(false);
          if (!disabled) addFiles([...event.dataTransfer.files]);
        }}
      >
        <span className="upload-icon">
          <UploadCloud size={26} />
        </span>
        <strong>Drop your transcripts here</strong>
        <span>
          or <b>browse files</b> to upload
        </span>
        <small>TXT, PDF, DOCX, CSV · up to {fileSize(maxBytes)} each</small>
      </button>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {!!files.length && (
        <div className="selected-files">
          {files.map((file, index) => (
            <div className="selected-file" key={`${file.name}-${file.size}`}>
              <FileText size={18} />
              <span>
                {file.name}
                <small>{fileSize(file.size)}</small>
              </span>
              <button
                type="button"
                disabled={disabled}
                className="icon-btn"
                aria-label={`Remove ${file.name}`}
                onClick={() => onChange(files.filter((_, i) => index !== i))}
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
