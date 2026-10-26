import { useEffect, useRef, useState, useCallback } from "react";
import "./Editor.css";

const API_URL = "http://127.0.0.1:8000";

const DEFAULT_SETTINGS = {
  sensitivity: 1.0,
  bright_cracks: true,
  dark_cracks: false,
  detect_dust: false,
  denoise: false,
  denoise_method: "nlm",
  denoise_strength: 25,
  fading: true,
  color_restore: true,
  sharpen: true,
};

const Editor = () => {
  const [originalUrl, setOriginalUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState(null);
  const [fileName, setFileName] = useState("");
  const [resultUrl, setResultUrl] = useState("");
  const [restorationDetails, setRestorationDetails] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [viewMode, setViewMode] = useState("split"); // "split" | "side" | "overlay" | "mask" | "restored"
  const [splitPos, setSplitPos] = useState(50);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [samples, setSamples] = useState([]);
  const [isSplitDragging, setIsSplitDragging] = useState(false);
  const splitContainerRef = useRef(null);

  // Fetch available test sample images from backend
  useEffect(() => {
    let isMounted = true;
    fetch(`${API_URL}/samples`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (isMounted && data?.samples?.length) {
          setSamples(data.samples);
        }
      })
      .catch(() => {
        // Backend not yet ready or offline; fail gracefully
      });
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (originalUrl && originalUrl.startsWith("blob:")) {
        URL.revokeObjectURL(originalUrl);
      }
    };
  }, [originalUrl]);

  const loadFile = useCallback((file) => {
    setError("");
    setNotice("");
    setResultUrl("");
    setRestorationDetails(null);

    if (!file) return;

    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      setError("Please choose a JPG, PNG, or WebP image.");
      return;
    }

    setSelectedFile(file);
    setOriginalUrl(URL.createObjectURL(file));
    setFileName(file.name);
  }, []);

  const handleFileChange = (event) => {
    const file = event.target.files?.[0];
    if (file) {
      loadFile(file);
    }
    event.target.value = "";
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDraggingFile(false);
    const file = event.dataTransfer?.files?.[0];
    if (file) {
      loadFile(file);
    }
  };

  const handleDragOver = (event) => {
    event.preventDefault();
    setIsDraggingFile(true);
  };

  const handleDragLeave = () => {
    setIsDraggingFile(false);
  };

  const loadSample = async (sample) => {
    if (isLoading) return;
    try {
      setIsLoading(true);
      setError("");
      setNotice("");
      const res = await fetch(`${API_URL}${sample.url}`);
      if (!res.ok) throw new Error("Could not load sample image.");
      const blob = await res.blob();
      const file = new File([blob], sample.filename, { type: blob.type });
      loadFile(file);
      setNotice(`Loaded sample photo: ${sample.name}`);
    } catch (err) {
      setError(err.message || "Failed to load sample image.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSettingChange = (name, value) => {
    setSettings((prev) => ({
      ...prev,
      [name]: value,
    }));
  };

  const resetSettings = () => {
    setSettings(DEFAULT_SETTINGS);
  };

  const handleProcess = async () => {
    if (!selectedFile || isLoading) return;

    setIsLoading(true);
    setError("");
    setNotice("");
    setResultUrl("");
    setRestorationDetails(null);

    try {
      const formData = new FormData();
      formData.append("file", selectedFile);
      formData.append("denoise", String(settings.denoise));
      formData.append("denoise_method", settings.denoise_method);
      formData.append("denoise_strength", String(settings.denoise_strength));
      formData.append("sensitivity", String(settings.sensitivity));
      formData.append("bright_cracks", String(settings.bright_cracks));
      formData.append("dark_cracks", String(settings.dark_cracks));
      formData.append("detect_dust", String(settings.detect_dust));
      formData.append("fading", String(settings.fading));
      formData.append("color_restore", String(settings.color_restore));
      formData.append("sharpen", String(settings.sharpen));
      formData.append("return_details", "true");

      const response = await fetch(`${API_URL}/restore`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        let message = "Image processing failed.";
        try {
          const data = await response.json();
          message = data.detail || message;
        } catch {
          // Keep default message
        }
        throw new Error(message);
      }

      const contentType = response.headers.get("content-type") || "";

      if (contentType.includes("application/json")) {
        const data = await response.json();
        setRestorationDetails(data);
        setResultUrl(data.restored_image);
        const percent = (data.coverage * 100).toFixed(1);
        setNotice(
          `Restoration complete! Repaired ${percent}% damage using ${data.backend_used} inpainting.`,
        );
      } else {
        const imageBlob = await response.blob();
        const url = URL.createObjectURL(imageBlob);
        setResultUrl(url);
        setNotice("Processing completed! Compare the original and restored result.");
      }
    } catch (err) {
      setError(
        err.message === "Failed to fetch"
          ? "Cannot connect to the backend. Make sure FastAPI is running on port 8000."
          : err.message || "Something went wrong while processing the image.",
      );
    } finally {
      setIsLoading(false);
    }
  };

  const downloadImage = (url, name) => {
    if (!url) return;
    const link = document.createElement("a");
    link.href = url;
    link.download = name;
    document.body.appendChild(link);
    link.click();
    link.remove();
  };

  // Split-slider dragging
  const updateSplitPos = useCallback((clientX) => {
    if (!splitContainerRef.current) return;
    const rect = splitContainerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(clientX - rect.left, rect.width));
    const percent = Math.round((x / rect.width) * 100);
    setSplitPos(percent);
  }, []);

  const handleSplitMouseDown = (e) => {
    setIsSplitDragging(true);
    updateSplitPos(e.clientX);
  };

  const handleSplitMouseMove = (e) => {
    if (!isSplitDragging) return;
    updateSplitPos(e.clientX);
  };

  const handleSplitMouseUp = () => {
    setIsSplitDragging(false);
  };

  const handleSplitTouchMove = (e) => {
    if (e.touches && e.touches[0]) {
      updateSplitPos(e.touches[0].clientX);
    }
  };

  return (
    <section className="editor-section" aria-labelledby="editor-title">
      <div className="editor-heading">
        <p className="editor-eyebrow">Interactive Digital Image Processing</p>
        <h2 id="editor-title">Photo Restoration Studio</h2>
        <p>
          Detect scratches and cracks, tune detection sensitivity, inpaint
          damaged areas, and restore contrast, color balance, and fine sharpness.
        </p>
      </div>

      {/* Upload Zone & Samples */}
      <div className="editor-top-bar">
        <div
          className={`editor-dropzone ${isDraggingFile ? "dragging" : ""}`}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
        >
          <label className="upload-label" htmlFor="photo-upload">
            <span className="upload-icon" aria-hidden="true">
              ↑
            </span>
            <span>
              <strong>Choose or drag &amp; drop a photograph</strong>
              <small>JPG, PNG, or WebP</small>
            </span>
          </label>

          <input
            id="photo-upload"
            className="file-input"
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={handleFileChange}
            disabled={isLoading}
          />
        </div>

        {samples.length > 0 && (
          <div className="sample-selector">
            <span className="sample-label">Or try a sample photo:</span>
            <div className="sample-buttons">
              {samples.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  className="sample-btn"
                  onClick={() => loadSample(s)}
                  disabled={isLoading}
                >
                  📸 {s.name}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {fileName && (
        <div className="selected-bar">
          <span>Active image: <strong>{fileName}</strong></span>
        </div>
      )}

      {error && (
        <p className="editor-message editor-error" role="alert">
          ⚠️ {error}
        </p>
      )}

      {notice && (
        <p className="editor-message editor-notice" role="status">
          ✓ {notice}
        </p>
      )}

      {restorationDetails?.warning && (
        <p className="editor-message editor-warning" role="alert">
          ℹ️ {restorationDetails.warning}
        </p>
      )}

      {/* Main Workspace */}
      <div className="editor-workspace">
        {/* Controls Column */}
        <section className="controls-panel" aria-labelledby="controls-title">
          <div className="panel-heading">
            <h3 id="controls-title">Restoration Controls</h3>
            <button
              type="button"
              className="reset-btn"
              onClick={resetSettings}
              disabled={isLoading}
              title="Reset all settings to default values"
            >
              Reset defaults
            </button>
          </div>

          <div className="controls-body">
            {/* Section 1: Damage Detection */}
            <div className="control-group">
              <h4 className="control-group-title">1. Damage Detection</h4>
              
              <div className="control-item slider-item">
                <div className="slider-header">
                  <label htmlFor="sensitivity-slider">
                    <strong>Detection Sensitivity</strong>
                  </label>
                  <span className="slider-value">{settings.sensitivity.toFixed(1)}x</span>
                </div>
                <input
                  id="sensitivity-slider"
                  type="range"
                  min="0.4"
                  max="1.8"
                  step="0.1"
                  value={settings.sensitivity}
                  onChange={(e) =>
                    handleSettingChange("sensitivity", parseFloat(e.target.value))
                  }
                  disabled={!selectedFile || isLoading}
                />
                <div className="slider-ticks">
                  <span>0.4 (Low)</span>
                  <span>1.0 (Balanced)</span>
                  <span>1.8 (Aggressive)</span>
                </div>
                <small className="control-hint">
                  Higher values catch faint cracks; lower values prevent mistaking facial texture for cracks.
                </small>
              </div>

              <label className="checkbox-item" htmlFor="bright-cracks">
                <input
                  id="bright-cracks"
                  type="checkbox"
                  checked={settings.bright_cracks}
                  onChange={(e) =>
                    handleSettingChange("bright_cracks", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Bright cracks &amp; white scratches</strong>
                  <small>Detects light physical abrasions and emulsion tears.</small>
                </span>
              </label>

              <label className="checkbox-item" htmlFor="dark-cracks">
                <input
                  id="dark-cracks"
                  type="checkbox"
                  checked={settings.dark_cracks}
                  onChange={(e) =>
                    handleSettingChange("dark_cracks", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Dark cracks &amp; black creases</strong>
                  <small>Detects dark fissures, folds, and ink marks.</small>
                </span>
              </label>

              <label className="checkbox-item" htmlFor="detect-dust">
                <input
                  id="detect-dust"
                  type="checkbox"
                  checked={settings.detect_dust}
                  onChange={(e) =>
                    handleSettingChange("detect_dust", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Dust spots &amp; film blemishes</strong>
                  <small>Morphological top-hat filter for compact spots.</small>
                </span>
              </label>
            </div>

            {/* Section 2: Denoising */}
            <div className="control-group">
              <h4 className="control-group-title">2. Pre-Restoration Denoising</h4>
              
              <label className="checkbox-item" htmlFor="remove-noise">
                <input
                  id="remove-noise"
                  name="denoise"
                  type="checkbox"
                  checked={settings.denoise}
                  onChange={(e) =>
                    handleSettingChange("denoise", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Apply noise reduction</strong>
                  <small>Smooths film grain before damage detection.</small>
                </span>
              </label>

              {settings.denoise && (
                <div className="sub-controls">
                  <div className="control-item">
                    <label htmlFor="denoise-method">Method</label>
                    <select
                      id="denoise-method"
                      value={settings.denoise_method}
                      onChange={(e) =>
                        handleSettingChange("denoise_method", e.target.value)
                      }
                      disabled={!selectedFile || isLoading}
                    >
                      <option value="nlm">Non-Local Means (Best Quality)</option>
                      <option value="gaussian">Gaussian Filter (Fast)</option>
                      <option value="median">Median Filter (Impulse)</option>
                    </select>
                  </div>

                  <div className="control-item slider-item">
                    <div className="slider-header">
                      <label htmlFor="denoise-strength">Denoise Strength</label>
                      <span className="slider-value">{settings.denoise_strength}</span>
                    </div>
                    <input
                      id="denoise-strength"
                      type="range"
                      min="5"
                      max="75"
                      step="5"
                      value={settings.denoise_strength}
                      onChange={(e) =>
                        handleSettingChange("denoise_strength", parseInt(e.target.value, 10))
                      }
                      disabled={!selectedFile || isLoading}
                    />
                  </div>
                </div>
              )}
            </div>

            {/* Section 3: Enhancement */}
            <div className="control-group">
              <h4 className="control-group-title">3. Post-Processing &amp; Enhancement</h4>
              
              <label className="checkbox-item" htmlFor="fading-correction">
                <input
                  id="fading-correction"
                  type="checkbox"
                  checked={settings.fading}
                  onChange={(e) =>
                    handleSettingChange("fading", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Contrast recovery (CLAHE)</strong>
                  <small>Adaptive histogram equalization for faded luminance.</small>
                </span>
              </label>

              <label className="checkbox-item" htmlFor="color-restore">
                <input
                  id="color-restore"
                  type="checkbox"
                  checked={settings.color_restore}
                  onChange={(e) =>
                    handleSettingChange("color_restore", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Chroma / Color balance recovery</strong>
                  <small>Gently recovers faded saturation without colorizing.</small>
                </span>
              </label>

              <label className="checkbox-item" htmlFor="sharpen-toggle">
                <input
                  id="sharpen-toggle"
                  type="checkbox"
                  checked={settings.sharpen}
                  onChange={(e) =>
                    handleSettingChange("sharpen", e.target.checked)
                  }
                  disabled={!selectedFile || isLoading}
                />
                <span>
                  <strong>Unsharp mask sharpening</strong>
                  <small>Brings out crisp edges and structural details.</small>
                </span>
              </label>
            </div>
          </div>

          <button
            className="editor-button process-button"
            type="button"
            onClick={handleProcess}
            disabled={!selectedFile || isLoading}
          >
            {isLoading ? "Restoring photograph…" : "⚡ Run Photo Restoration"}
          </button>
        </section>

        {/* Display / Results Column */}
        <section className="display-panel" aria-label="Restoration visual studio">
          <div className="panel-heading">
            <div className="view-mode-tabs" role="tablist" aria-label="Display mode">
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "split"}
                className={`tab-btn ${viewMode === "split" ? "active" : ""}`}
                onClick={() => setViewMode("split")}
                disabled={!resultUrl}
              >
                🔀 Split Compare
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "side"}
                className={`tab-btn ${viewMode === "side" ? "active" : ""}`}
                onClick={() => setViewMode("side")}
                disabled={!resultUrl}
              >
                🖼️ Side-by-Side
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "overlay"}
                className={`tab-btn ${viewMode === "overlay" ? "active" : ""}`}
                onClick={() => setViewMode("overlay")}
                disabled={!restorationDetails?.damage_overlay}
              >
                🔴 Damage Overlay
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "mask"}
                className={`tab-btn ${viewMode === "mask" ? "active" : ""}`}
                onClick={() => setViewMode("mask")}
                disabled={!restorationDetails?.damage_mask}
              >
                ⬛ Damage Mask
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={viewMode === "restored"}
                className={`tab-btn ${viewMode === "restored" ? "active" : ""}`}
                onClick={() => setViewMode("restored")}
                disabled={!resultUrl}
              >
                ✨ Restored Only
              </button>
            </div>

            {restorationDetails && (
              <span className="coverage-badge">
                {(restorationDetails.coverage * 100).toFixed(1)}% repaired
              </span>
            )}
          </div>

          <div
            className="visual-stage"
            onMouseUp={handleSplitMouseUp}
            onMouseLeave={handleSplitMouseUp}
          >
            {!originalUrl && (
              <div className="empty-stage">
                <span className="empty-icon" aria-hidden="true">🖼️</span>
                <p>Choose an image or select a sample photo to begin.</p>
              </div>
            )}

            {originalUrl && !resultUrl && (
              <div className="single-preview">
                <img src={originalUrl} alt={`Original: ${fileName}`} />
                <span className="stage-caption">Original Input Photo</span>
              </div>
            )}

            {originalUrl && resultUrl && (
              <>
                {viewMode === "split" && (
                  <div
                    className="split-comparison-container"
                    ref={splitContainerRef}
                    onMouseDown={handleSplitMouseDown}
                    onMouseMove={handleSplitMouseMove}
                    onTouchMove={handleSplitTouchMove}
                  >
                    <img
                      src={originalUrl}
                      alt="Original"
                      className="split-img split-original"
                      draggable={false}
                    />
                    <div
                      className="split-overlay-wrapper"
                      style={{ clipPath: `inset(0 0 0 ${splitPos}%)` }}
                    >
                      <img
                        src={resultUrl}
                        alt="Restored"
                        className="split-img split-restored"
                        draggable={false}
                      />
                    </div>
                    <div
                      className="split-divider"
                      style={{ left: `${splitPos}%` }}
                    >
                      <div className="split-handle" aria-hidden="true">
                        <span>◀ ▶</span>
                      </div>
                    </div>
                    <span className="split-label split-label-left">Original</span>
                    <span className="split-label split-label-right">Restored</span>
                  </div>
                )}

                {viewMode === "side" && (
                  <div className="side-by-side-container">
                    <div className="side-item">
                      <span className="side-label">Original</span>
                      <img src={originalUrl} alt="Original input" />
                    </div>
                    <div className="side-item">
                      <span className="side-label">Restored Result</span>
                      <img src={resultUrl} alt="Restored output" />
                    </div>
                  </div>
                )}

                {viewMode === "overlay" && restorationDetails?.damage_overlay && (
                  <div className="single-preview">
                    <img
                      src={restorationDetails.damage_overlay}
                      alt="Damage overlay highlighting cracks in red"
                    />
                    <span className="stage-caption">Detected Damage Overlay (Red)</span>
                  </div>
                )}

                {viewMode === "mask" && restorationDetails?.damage_mask && (
                  <div className="single-preview mask-view">
                    <img
                      src={restorationDetails.damage_mask}
                      alt="Binary damage mask"
                    />
                    <span className="stage-caption">Binary Inpainting Mask</span>
                  </div>
                )}

                {viewMode === "restored" && (
                  <div className="single-preview">
                    <img src={resultUrl} alt="Restored output" />
                    <span className="stage-caption">Final Restored Photograph</span>
                  </div>
                )}
              </>
            )}
          </div>

          {/* Pipeline execution step tags */}
          {restorationDetails?.steps && (
            <div className="execution-steps">
              <span className="steps-title">Applied Pipeline Stages:</span>
              <div className="step-tags">
                {restorationDetails.steps.map((step, idx) => (
                  <span key={idx} className="step-tag">
                    ✓ {step}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Download and action buttons */}
          <div className="download-bar">
            <button
              className="editor-button download-btn primary-download"
              type="button"
              onClick={() =>
                downloadImage(
                  resultUrl,
                  `${fileName.replace(/\.[^.]+$/, "")}-restored.png`,
                )
              }
              disabled={!resultUrl || isLoading}
            >
              📥 Download Restored PNG
            </button>

            {restorationDetails?.damage_mask && (
              <button
                className="editor-button download-btn secondary-download"
                type="button"
                onClick={() =>
                  downloadImage(
                    restorationDetails.damage_mask,
                    `${fileName.replace(/\.[^.]+$/, "")}-mask.png`,
                  )
                }
                disabled={isLoading}
              >
                ⬛ Download Mask
              </button>
            )}

            <button
              className="editor-button download-btn secondary-download"
              type="button"
              onClick={() =>
                downloadImage(originalUrl, fileName || "original.png")
              }
              disabled={!originalUrl || isLoading}
            >
              📷 Download Original
            </button>
          </div>
        </section>
      </div>
    </section>
  );
};

export default Editor;
