document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.getElementById("dropzone");
  const fileInput = document.getElementById("file-input");
  const browseBtn = document.getElementById("browse-btn");
  const processBtn = document.getElementById("process-btn");
  const statusEl = document.getElementById("upload-status");

  const resultsPlaceholder = document.getElementById("results-placeholder");
  const resultsContainer = document.getElementById("results");
  const pagesViewer = document.getElementById("pages-viewer");
  const jsonViewer = document.getElementById("json-viewer");
  const downloadJsonBtn = document.getElementById("download-json-btn");
  const statsImage = document.getElementById("stats-image");
  const statsSummary = document.getElementById("stats-summary");

  const summaryCard = document.getElementById("summary-card");
  const summaryDocs = document.getElementById("summary-docs");
  const summaryPages = document.getElementById("summary-pages");
  const summaryObjects = document.getElementById("summary-objects");
  const summaryBreakdown = document.getElementById("summary-breakdown");

  const viewerOverlay = document.getElementById("viewer-overlay");
  const viewerImage = document.getElementById("viewer-image");
  const viewerTitle = document.getElementById("viewer-title");
  const viewerPageIndicator = document.getElementById("viewer-page-indicator");
  const viewerPrevBtn = document.getElementById("viewer-prev");
  const viewerNextBtn = document.getElementById("viewer-next");
  const viewerCloseBtn = document.getElementById("viewer-close");

  let selectedFiles = [];
  let lastResponse = null;

  let currentDoc = null;
  let currentPageIndex = 0;

  function updateStatus() {
    if (!selectedFiles.length) {
      statusEl.textContent = "No files selected yet.";
      processBtn.disabled = true;
    } else {
      const names = selectedFiles.map(f => f.name).join(", ");
      statusEl.textContent = `Selected ${selectedFiles.length} file(s): ${names}`;
      processBtn.disabled = false;
    }
  }

  function setFilesFromList(fileList) {
    selectedFiles = Array.from(fileList).filter(file => {
      const name = file.name.toLowerCase();
      return name.endsWith(".pdf") || name.endsWith(".zip");
    });
    if (fileList.length && !selectedFiles.length) {
      statusEl.textContent = "Unsupported format. Please upload PDF or ZIP files.";
      processBtn.disabled = true;
      return;
    }
    updateStatus();
  }

  if (dropzone) {
    dropzone.addEventListener("dragover", event => {
      event.preventDefault();
      dropzone.classList.add("upload-dropzone--active");
    });

    dropzone.addEventListener("dragleave", event => {
      event.preventDefault();
      dropzone.classList.remove("upload-dropzone--active");
    });

    dropzone.addEventListener("drop", event => {
      event.preventDefault();
      dropzone.classList.remove("upload-dropzone--active");
      if (event.dataTransfer && event.dataTransfer.files) {
        setFilesFromList(event.dataTransfer.files);
      }
    });

    dropzone.addEventListener("click", () => {
      fileInput && fileInput.click();
    });

    dropzone.addEventListener("keydown", event => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        fileInput && fileInput.click();
      }
    });
  }

  if (browseBtn) {
    browseBtn.addEventListener("click", () => {
      fileInput && fileInput.click();
    });
  }

  if (fileInput) {
    fileInput.addEventListener("change", event => {
      if (event.target.files) {
        setFilesFromList(event.target.files);
      }
    });
  }

  async function processFiles() {
    if (!selectedFiles.length) return;

    const formData = new FormData();
    selectedFiles.forEach(file => {
      formData.append("files", file);
    });

    processBtn.disabled = true;
    processBtn.textContent = "Processing...";
    statusEl.textContent = "Uploading and processing… this may take a bit for many pages.";
    resultsPlaceholder.hidden = false;
    resultsContainer.hidden = true;

    try {
      const response = await fetch("/api/process", {
        method: "POST",
        body: formData
      });

      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `Server error (${response.status})`);
      }

      const data = await response.json();
      lastResponse = data;
      renderResults(data);
      statusEl.textContent = "Processing finished successfully.";
    } catch (error) {
      console.error(error);
      alert("Error while processing documents: " + error.message);
      statusEl.textContent = "Error. Please try again or check the server logs.";
    } finally {
      processBtn.disabled = !selectedFiles.length;
      processBtn.textContent = "Run QubrixAI analysis";
    }
  }

  function renderResults(data) {
    if (!data || !data.documents) {
      return;
    }

    resultsPlaceholder.hidden = true;
    resultsContainer.hidden = false;

    if (data.summary && summaryCard) {
      const { total_documents, total_pages, total_objects, by_type } = data.summary;

      summaryDocs.textContent = total_documents ?? 0;
      summaryPages.textContent = total_pages ?? 0;
      summaryObjects.textContent = total_objects ?? 0;

      if (by_type) {
        const parts = Object.keys(by_type).map(key => `${key}: ${by_type[key]}`);
        summaryBreakdown.textContent = parts.join(" • ");
      } else {
        summaryBreakdown.textContent = "";
      }

      summaryCard.hidden = false;
    }

    pagesViewer.innerHTML = "";

    data.documents.forEach(doc => {
      const pages = doc.pages || [];
      if (!pages.length) return;

      const firstPage = pages[0];

      let sigCount = 0;
      let stampCount = 0;
      let qrCount = 0;

      pages.forEach(page => {
        const objects = page.objects || [];
        sigCount += objects.filter(o => o.type === "signature").length;
        stampCount += objects.filter(o => o.type === "stamp").length;
        qrCount += objects.filter(o => o.type === "qrcode").length;
      });

      const docCard = document.createElement("button");
      docCard.type = "button";
      docCard.className = "doc-card";

      const thumbWrap = document.createElement("div");
      thumbWrap.className = "doc-card__thumb-wrap";

      const thumbImg = document.createElement("img");
      thumbImg.className = "doc-card__thumb";
      thumbImg.loading = "lazy";
      thumbImg.src = firstPage.image_url;
      thumbImg.alt = `First page of ${doc.original_filename || "document.pdf"}`;

      thumbWrap.appendChild(thumbImg);

      const meta = document.createElement("div");
      meta.className = "doc-card__meta";

      const title = document.createElement("div");
      title.className = "doc-card__title";
      title.textContent = doc.original_filename || "document.pdf";

      const info = document.createElement("div");
      info.className = "doc-card__info";
      const pagesCount = pages.length;
      const parts = [];
      parts.push(`${pagesCount} page${pagesCount === 1 ? "" : "s"}`);
      if (sigCount) parts.push(`S: ${sigCount}`);
      if (stampCount) parts.push(`St: ${stampCount}`);
      if (qrCount) parts.push(`QR: ${qrCount}`);
      info.textContent = parts.join(" • ");

      meta.appendChild(title);
      meta.appendChild(info);

      docCard.appendChild(thumbWrap);
      docCard.appendChild(meta);

      docCard.addEventListener("click", () => {
        openViewer(doc, 0);
      });

      pagesViewer.appendChild(docCard);
    });

    jsonViewer.textContent = JSON.stringify(data, null, 2);

    if (data.summary && data.summary.stats_image_url) {
      statsImage.src = data.summary.stats_image_url;
      statsImage.hidden = false;
    } else {
      statsImage.hidden = true;
    }

    if (data.summary) {
      const { by_type } = data.summary;
      if (by_type) {
        const total =
          (by_type.signature || 0) +
          (by_type.stamp || 0) +
          (by_type.qrcode || 0);

        const textParts = [];
        if (total > 0) {
          if (by_type.signature) {
            textParts.push(
              `${by_type.signature} signatures (${Math.round(
                (by_type.signature / total) * 100
              )}%)`
            );
          }
          if (by_type.stamp) {
            textParts.push(
              `${by_type.stamp} stamps (${Math.round(
                (by_type.stamp / total) * 100
              )}%)`
            );
          }
          if (by_type.qrcode) {
            textParts.push(
              `${by_type.qrcode} QR codes (${Math.round(
                (by_type.qrcode / total) * 100
              )}%)`
            );
          }
        }
        statsSummary.textContent = textParts.join(" • ");
      } else {
        statsSummary.textContent = "";
      }
    }
  }

  function updateViewerPage() {
    if (!currentDoc || !currentDoc.pages || !currentDoc.pages.length) {
      return;
    }

    if (currentPageIndex < 0) currentPageIndex = 0;
    if (currentPageIndex >= currentDoc.pages.length) {
      currentPageIndex = currentDoc.pages.length - 1;
    }

    const page = currentDoc.pages[currentPageIndex];
    if (!page) return;

    if (viewerImage) {
      viewerImage.src = page.image_url;
      viewerImage.alt = `Annotated page ${page.page_number} of ${currentDoc.original_filename || "document.pdf"}`;
    }

    if (viewerTitle) {
      viewerTitle.textContent = currentDoc.original_filename || "document.pdf";
    }

    if (viewerPageIndicator) {
      viewerPageIndicator.textContent = `Page ${page.page_number} of ${currentDoc.pages.length}`;
    }

    if (viewerPrevBtn && viewerNextBtn) {
      if (currentDoc.pages.length <= 1) {
        viewerPrevBtn.disabled = true;
        viewerNextBtn.disabled = true;
      } else {
        viewerPrevBtn.disabled = currentPageIndex === 0;
        viewerNextBtn.disabled = currentPageIndex === currentDoc.pages.length - 1;
      }
    }
  }

  function openViewer(doc, pageIndex) {
    if (!doc || !doc.pages || !doc.pages.length || !viewerOverlay) return;

    currentDoc = doc;
    currentPageIndex = typeof pageIndex === "number" ? pageIndex : 0;

    updateViewerPage();

    viewerOverlay.hidden = false;
    viewerOverlay.setAttribute("aria-hidden", "false");
    document.body.classList.add("no-scroll");
  }

  function closeViewer() {
    if (!viewerOverlay) return;
    viewerOverlay.hidden = true;
    viewerOverlay.setAttribute("aria-hidden", "true");
    document.body.classList.remove("no-scroll");
    currentDoc = null;
    currentPageIndex = 0;
  }

  if (viewerPrevBtn) {
    viewerPrevBtn.addEventListener("click", () => {
      if (!currentDoc) return;
      currentPageIndex -= 1;
      updateViewerPage();
    });
  }

  if (viewerNextBtn) {
    viewerNextBtn.addEventListener("click", () => {
      if (!currentDoc) return;
      currentPageIndex += 1;
      updateViewerPage();
    });
  }

  if (viewerCloseBtn) {
    viewerCloseBtn.addEventListener("click", () => {
      closeViewer();
    });
  }

  if (viewerOverlay) {
    viewerOverlay.addEventListener("click", event => {
      if (event.target === viewerOverlay) {
        closeViewer();
      }
    });
  }

  function handleKeydown(event) {
    if (!viewerOverlay || viewerOverlay.hidden) return;

    if (event.key === "Escape") {
      event.preventDefault();
      closeViewer();
      return;
    }

    if (!currentDoc || !currentDoc.pages || !currentDoc.pages.length) return;

    if (event.key === "ArrowLeft") {
      if (currentPageIndex > 0) {
        event.preventDefault();
        currentPageIndex -= 1;
        updateViewerPage();
      }
    } else if (event.key === "ArrowRight") {
      if (currentPageIndex < currentDoc.pages.length - 1) {
        event.preventDefault();
        currentPageIndex += 1;
        updateViewerPage();
      }
    }
  }

  document.addEventListener("keydown", handleKeydown);

  if (processBtn) {
    processBtn.addEventListener("click", () => {
      void processFiles();
    });
  }

  if (downloadJsonBtn) {
    downloadJsonBtn.addEventListener("click", () => {
      if (!lastResponse) return;
      const blob = new Blob([JSON.stringify(lastResponse, null, 2)], {
        type: "application/json"
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "qubrixai_results.json";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    });
  }
});
