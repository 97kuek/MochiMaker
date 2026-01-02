import { useState, useEffect } from 'react';
import { DropZone } from './components/DropZone';
import { Controls } from './components/Controls';
import { SortableItem } from './components/SortableItem';
import { CanvasPreview } from './components/CanvasPreview';
import { loadPDF, renderPageToCanvas, type PDFPageData } from './utils/pdfProcessor';

import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  DragOverlay,
  type DragStartEvent,
  type DragEndEvent
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  rectSortingStrategy,
} from '@dnd-kit/sortable';

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
  const [title, setTitle] = useState('');
  const [activeId, setActiveId] = useState<string | null>(null);

  // Robust sensors for both Mouse and Touch
  const sensors = useSensors(
    useSensor(MouseSensor, {
      activationConstraint: {
        distance: 10, // Avoid accidental drags on click
      },
    }),
    useSensor(TouchSensor, {
      activationConstraint: {
        delay: 250, // Hold to drag
        tolerance: 5, // Allow slight movement during hold
      },
    }),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleFilesSelect = async (selectedFiles: File[]) => {
    // Append unique files based on name/size/timestamp if possible, but File equality is tricky.
    // For now, simple append.
    setFiles(prev => [...prev, ...selectedFiles]);
    setLoading(true);

    const newPages: PDFPageData[] = [];

    try {
      for (const file of selectedFiles) {
        // Wrap in try-catch per file to avoid total failure
        try {
          const pdf = await loadPDF(file);
          const totalPages = pdf.numPages;

          for (let i = 1; i <= totalPages; i++) {
            const pageData = await renderPageToCanvas(pdf, i, 2.0); // Render at 2x scale for quality
            newPages.push({ ...pageData, id: `${file.name}-${i}-${crypto.randomUUID()}` });
            setProcessedCount(prev => prev + 1);
          }
        } catch (fileErr) {
          console.error(`Failed to load file ${file.name}:`, fileErr);
          alert(`Error loading ${file.name}. It might be corrupted or password protected.`);
        }
      }

      setPages(prev => [...prev, ...newPages]);
    } catch (error) {
      console.error('Critical error processing PDFs:', error);
      alert('An unexpected error occurred. Please reload and try again.');
    } finally {
      setLoading(false);
    }
  };

  const handleClearAll = () => {
    if (confirm('Are you sure you want to clear all pages?')) {
      setFiles([]);
      setPages([]);
      setProcessedCount(0);
      setTitle('');
    }
  };

  const handleDeletePage = (idToDelete: string) => {
    setPages(prev => prev.filter(p => p.id !== idToDelete));
  };

  const handlePrint = () => {
    window.print();
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      setPages((items) => {
        const oldIndex = items.findIndex((item) => item.id === active.id);
        const newIndex = items.findIndex((item) => item.id === over.id);
        return arrayMove(items, oldIndex, newIndex);
      });
    }

    setActiveId(null);
  };

  const getPaperStyle = () => {
    const size = PAPER_SIZES[paperSize];
    if (orientation === 'landscape') {
      return { width: size.height, height: size.width };
    }
    return size;
  };

  const paperStyle = getPaperStyle();

  // Inject dynamic print styles
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

    // We strictly force the size and remove browser margins.
    styleEl.innerHTML = `
      @media print {
        @page {
          size: ${sizeCSS};
          margin: 0;
        }
        /* Extra safety: override any bootstrap/browser styles */
        body { margin: 0; padding: 0; }
        
        /* STRICTLY FORCE DIMENSIONS */
        .a4-page {
           width: ${sizeCSS.split(' ')[0]} !important;
           height: ${sizeCSS.split(' ')[1]} !important;
           min-height: ${sizeCSS.split(' ')[1]} !important;
           max-height: ${sizeCSS.split(' ')[1]} !important;
        }
      }
    `;
  }, [paperSize, orientation]);

  const itemsPerPage = layout.rows * layout.cols;
  const totalGridPages = pages.length > 0 ? Math.ceil(pages.length / itemsPerPage) : 0;

  const activePage = activeId ? pages.find(p => p.id === activeId) : null;

  // Render logic safely
  const renderGridPages = () => {
    const gridPagesElements = [];

    for (let i = 0; i < totalGridPages; i++) {
      const startIndex = i * itemsPerPage;
      const pageItems = pages.slice(startIndex, startIndex + itemsPerPage).map((p) => {
        return (
          <SortableItem key={p.id} id={p.id} className="grid-item-container">
            <div style={{ position: 'relative', width: '100%', height: '100%', overflow: 'hidden' }}>
              <CanvasPreview canvas={p.canvas} />
              <button
                onPointerDown={(e) => e.stopPropagation()}
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeletePage(p.id);
                }}
                className="delete-overlay"
                type="button" // Important preventing form submission if any
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
                  zIndex: 10,
                  fontSize: '16px',
                  lineHeight: 1
                }}
                title="Remove Slide"
                aria-label="Remove Slide"
              >
                ×
              </button>
            </div>
          </SortableItem>
        );
      });

      gridPagesElements.push(
        <div
          key={i}
          className="a4-page"
          style={{
            width: paperStyle.width,
            minHeight: paperStyle.height,
            height: paperStyle.height, // Strict height for flex distribution
            display: 'flex',
            flexDirection: 'column',
            padding: '10mm',
            boxSizing: 'border-box',
            backgroundColor: 'white',
            position: 'relative'
          }}
        >
          {title && (
            <div style={{
              marginBottom: '5mm',
              textAlign: 'center',
              fontWeight: 'bold',
              fontSize: '18px',
              borderBottom: '2px solid #333',
              paddingBottom: '2mm',
              flexShrink: 0 // Prevent shrinking
            }}>
              {title}
            </div>
          )}

          <div style={{
            flex: 1,
            display: 'grid',
            gridTemplateColumns: `repeat(${layout.cols}, minmax(0, 1fr))`, // minmax(0,1fr) prevents overflow
            gridTemplateRows: `repeat(${layout.rows}, minmax(0, 1fr))`,
            gap: `${gap}px`,
            width: '100%',
            overflow: 'hidden' // strict container
          }}>
            {pageItems.map((item, idx) => (
              <div key={idx} className="grid-item" style={{
                position: 'relative',
                width: '100%',
                height: '100%',
                overflow: 'hidden'
              }}>
                {item}
              </div>
            ))}
          </div>

          <div style={{
            position: 'absolute',
            bottom: '5mm', // Use exact positioning relative to page edge
            right: '10mm',
            fontSize: '10px',
            color: '#999',
            pointerEvents: 'none'
          }}>
            Page {i + 1}
          </div>
        </div>
      );
    }
    return gridPagesElements;
  };

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
        title={title}
        setTitle={setTitle}
      />

      <main className="main-content">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={pages.map(p => p.id)}
            strategy={rectSortingStrategy}
          >
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
                {renderGridPages()}

                {/* Only show DropZone at bottom if not printing. Handled by CSS media print mostly, but safe to keep here. */}
                <div className="dropzone-footer" style={{ margin: '2rem 0', maxWidth: '600px', width: '100%' }}>
                  <DropZone onFilesSelect={handleFilesSelect} />
                </div>
              </div>
            )}
          </SortableContext>

          <DragOverlay adjustScale={true}>
            {activePage ? (
              <div className="grid-item" style={{
                width: '150px', // Smaller drag preview
                height: 'auto',
                background: 'white',
                boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
                border: '2px solid #2563eb',
                borderRadius: '0.5rem',
                overflow: 'hidden',
                opacity: 0.9
              }}>
                <CanvasPreview canvas={activePage.canvas} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>
    </div>
  );
}

export default App;
