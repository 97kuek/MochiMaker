import React, { useState, useEffect, useRef } from 'react';
import { DropZone } from './components/DropZone';
import { Controls } from './components/Controls';

import { loadPDF, renderPageToCanvas, type PDFPageData } from './utils/pdfProcessor';

// Helper to render provided canvas element into a div
const CanvasPreview: React.FC<{ canvas: HTMLCanvasElement }> = ({ canvas }) => {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.innerHTML = '';
      // Clone canvas or use image data to avoid "node already used" issues if we re-render?
      // Actually, since we only show each page once, we can append the original canvas.
      // But if we change layout, we might re-mount.
      // Appending the same canvas instance is fine as long as we don't try to append it to two places.
      canvas.style.width = '100%';
      canvas.style.height = '100%';
      canvas.style.objectFit = 'contain';
      containerRef.current.appendChild(canvas);
    }
  }, [canvas]);

  return <div ref={containerRef} style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }} />;
};

const PAPER_SIZES: Record<string, { width: string; height: string }> = {
  a4: { width: '210mm', height: '297mm' },
  a3: { width: '297mm', height: '420mm' },
  b5: { width: '176mm', height: '250mm' },
  b4: { width: '250mm', height: '353mm' },
  letter: { width: '216mm', height: '279mm' },
};

function App() {
  const [files, setFiles] = useState<File[]>([]);
  const [pages, setPages] = useState<PDFPageData[]>([]);
  const [layout, setLayout] = useState({ rows: 2, cols: 2 });
  const [gap, setGap] = useState(10);
  const [paperSize, setPaperSize] = useState('a4');
  const [orientation, setOrientation] = useState<'portrait' | 'landscape'>('portrait');
  const [loading, setLoading] = useState(false);
  const [processedCount, setProcessedCount] = useState(0);

  // Appending logic: add to existing files/pages instead of replacing
  const handleFilesSelect = async (selectedFiles: File[]) => {
    // Append files
    setFiles(prev => [...prev, ...selectedFiles]);
    setLoading(true);
    // Don't reset processed count, just add to it contextually or reset for this batch
    // Actually, let's just show "Processing..." and the increment

    const newPages: PDFPageData[] = [];

    try {
      for (const file of selectedFiles) {
        const pdf = await loadPDF(file);
        const totalPages = pdf.numPages;

        for (let i = 1; i <= totalPages; i++) {
          const pageData = await renderPageToCanvas(pdf, i, 2.0);
          newPages.push(pageData);
          setProcessedCount(prev => prev + 1);
        }
      }

      setPages(prev => [...prev, ...newPages]);
    } catch (error) {
      console.error('Error processing PDF:', error);
      alert('Failed to load PDF. See console for details.');
    } finally {
      setLoading(false);
    }
  };

  const handleClearAll = () => {
    if (confirm('Are you sure you want to clear all pages?')) {
      setFiles([]);
      setPages([]);
      setProcessedCount(0);
    }
  };

  const handleDeletePage = (indexToDelete: number) => {
    setPages(prev => prev.filter((_, idx) => idx !== indexToDelete));
  };

  const handlePrint = () => {
    window.print();
  };

  // Calculate dynamic paper dimensions
  const getPaperStyle = () => {
    const size = PAPER_SIZES[paperSize];
    if (orientation === 'landscape') {
      return { width: size.height, height: size.width };
    }
    return size;
  };

  const paperStyle = getPaperStyle();

  // Inject print styles dynamically
  useEffect(() => {
    const styleId = 'dynamic-print-style';
    let styleEl = document.getElementById(styleId) as HTMLStyleElement;
    if (!styleEl) {
      styleEl = document.createElement('style');
      styleEl.id = styleId;
      document.head.appendChild(styleEl);
    }

    const sizeCSS = orientation === 'landscape'
      ? `${PAPER_SIZES[paperSize].height} ${PAPER_SIZES[paperSize].width}`
      : `${PAPER_SIZES[paperSize].width} ${PAPER_SIZES[paperSize].height}`;

    styleEl.innerHTML = `
      @media print {
        @page {
          size: ${sizeCSS};
          margin: 0;
        }
        .a4-page {
          width: ${sizeCSS.split(' ')[0]} !important;
          min-height: ${sizeCSS.split(' ')[1]} !important;
        }
      }
    `;
  }, [paperSize, orientation]);

  // Pagination Logic
  const itemsPerPage = layout.rows * layout.cols;
  const totalGridPages = pages.length > 0 ? Math.ceil(pages.length / itemsPerPage) : 0;

  const gridPages = [];
  if (pages.length > 0) {
    for (let i = 0; i < totalGridPages; i++) {
      const startIndex = i * itemsPerPage;
      const pageItems = pages.slice(startIndex, startIndex + itemsPerPage).map((p, idx) => {
        const actualIndex = startIndex + idx;
        return (
          <div key={`${i}-${idx}`} style={{ position: 'relative', width: '100%', height: '100%' }} className="grid-item-container">
            <CanvasPreview canvas={p.canvas} />
            <button
              onClick={() => handleDeletePage(actualIndex)}
              className="delete-overlay"
              style={{
                position: 'absolute',
                top: '5px',
                right: '5px',
                background: 'rgba(239, 68, 68, 0.9)',
                color: 'white',
                border: 'none',
                borderRadius: '50%',
                width: '24px',
                height: '24px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer',
                zIndex: 10
              }}
              title="Remove Slide"
            >
              ×
            </button>
          </div>
        );
      });

      gridPages.push(
        <div
          key={i}
          className="a4-page" // We keep class name for CSS but override style
          style={{
            width: paperStyle.width,
            minHeight: paperStyle.height,
            display: 'grid',
            gridTemplateColumns: `repeat(${layout.cols}, 1fr)`,
            gap: `${gap}px`,
            // Force rows to be equal height if we want 2025 modern look
            gridTemplateRows: `repeat(${layout.rows}, 1fr)`,
            // We need to constrain height to the page minus padding
            height: paperStyle.height // specific height for grid calculation
          }}
        >
          {pageItems.map((item, idx) => (
            <div key={idx} className="grid-item" style={{ position: 'relative' }}>
              {item}
            </div>
          ))}

          {/* Page Number */}
          <div style={{
            position: 'absolute',
            bottom: '5mm',
            right: '10mm',
            fontSize: '10px',
            color: '#ccc',
            pointerEvents: 'none'
          }}>
            Page {i + 1}
          </div>
        </div>
      );
    }
  }

  return (
    <div className="app-container">
      <Controls
        layout={layout}
        setLayout={setLayout}
        gap={gap}
        setGap={setGap}
        paperSize={paperSize}
        setPaperSize={setPaperSize}
        orientation={orientation}
        setOrientation={setOrientation}
        onPrint={handlePrint}
        fileCount={files.length}
        onClearAll={handleClearAll}
      />

      <main className="main-content">
        {loading ? (
          <div style={{ marginTop: '5rem', textAlign: 'center' }}>
            <div className="loader" style={{ marginBottom: '1rem', fontSize: '1.5rem', fontWeight: 600 }}>
              Processing PDFs...
            </div>
            <p>Rendered {processedCount} pages</p>
          </div>
        ) : pages.length === 0 ? (
          <div style={{ marginTop: '5rem', width: '100%' }}>
            <DropZone onFilesSelect={handleFilesSelect} />
          </div>
        ) : (
          <div className="preview-area">
            {/* Show dropzone at bottom for appending? Or maybe a small button?
                 Actually, just keeping dropzone visible if empty is fine, but for append mode,
                 we might want a "Add more" button or area.
                 For now, let's keep it simple: if pages exist, maybe show a small drop area or
                 rely on a button in Controls? Actually, user spec said DropZone adds.
                 Let's add a small DropZone at the bottom of the list or a floating one.
             */}
            {gridPages}

            <div style={{ margin: '2rem 0', maxWidth: '600px', width: '100%' }}>
              <DropZone onFilesSelect={handleFilesSelect} />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
