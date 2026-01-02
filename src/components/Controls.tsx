import React from 'react';
import { Printer, Trash2 } from 'lucide-react';

interface ControlsProps {
    layout: { rows: number; cols: number };
    setLayout: (layout: { rows: number; cols: number }) => void;
    gap: number;
    setGap: (gap: number) => void;
    paperSize: string;
    setPaperSize: (size: string) => void;
    orientation: 'portrait' | 'landscape';
    setOrientation: (orientation: 'portrait' | 'landscape') => void;
    onPrint: () => void;
    fileCount: number;
    onClearAll: () => void;
    title: string;
    setTitle: (title: string) => void;
}

export const Controls: React.FC<ControlsProps> = ({
    layout,
    setLayout,
    gap,
    setGap,
    paperSize,
    setPaperSize,
    orientation,
    setOrientation,
    onPrint,
    fileCount,
    onClearAll,
    title,
    setTitle
}) => {
    const presets = [
        { label: '1x1', rows: 1, cols: 1 },
        { label: '1x2', rows: 1, cols: 2 },
        { label: '2x2', rows: 2, cols: 2 },
        { label: '2x3', rows: 2, cols: 3 },
        { label: '3x3', rows: 3, cols: 3 },
        { label: '4x4', rows: 4, cols: 4 },
    ];

    return (
        <header className="controls-header" style={{ flexWrap: 'wrap', gap: '1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
                <div style={{ fontWeight: 700, fontSize: '1.25rem', color: '#2563eb' }}>
                    MochiMaker
                </div>
                <div style={{ color: '#9ca3af', fontSize: '1.25rem' }}>/</div>
                {/* Title Input */}
                <input
                    type="text"
                    placeholder="Document Title (Header)"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    style={{
                        border: 'none',
                        borderBottom: '1px solid #ccc',
                        outline: 'none',
                        fontSize: '1rem',
                        padding: '0.25rem',
                        minWidth: '200px',
                        fontWeight: 500
                    }}
                />
            </div>

            <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem', flexWrap: 'wrap', flex: 1 }}>
                {/* Paper Settings */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6b7280' }}>
                        PAPER
                    </label>
                    <div style={{ display: 'flex', gap: '0.5rem' }}>
                        <select
                            value={paperSize}
                            onChange={(e) => setPaperSize(e.target.value)}
                            style={{ padding: '0.25rem', borderRadius: '0.25rem', border: '1px solid #d1d5db' }}
                        >
                            <option value="a4">A4</option>
                            <option value="a3">A3</option>
                            <option value="b5">B5</option>
                            <option value="b4">B4</option>
                            <option value="letter">Letter</option>
                        </select>
                        <select
                            value={orientation}
                            onChange={(e) => setOrientation(e.target.value as 'portrait' | 'landscape')}
                            style={{ padding: '0.25rem', borderRadius: '0.25rem', border: '1px solid #d1d5db' }}
                        >
                            <option value="portrait">Portrait</option>
                            <option value="landscape">Landscape</option>
                        </select>
                    </div>
                </div>

                <div className="divider" style={{ width: '1px', height: '32px', backgroundColor: '#e5e7eb' }}></div>

                {/* Layout Controls */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flexWrap: 'wrap' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6b7280' }}>
                            GRID
                        </label>
                        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                            {presets.map(p => (
                                <button
                                    key={p.label}
                                    onClick={() => setLayout({ rows: p.rows, cols: p.cols })}
                                    style={{
                                        padding: '0.25rem 0.5rem',
                                        borderRadius: '0.25rem',
                                        fontSize: '0.75rem',
                                        backgroundColor: (layout.rows === p.rows && layout.cols === p.cols) ? '#dbeafe' : 'transparent',
                                        color: (layout.rows === p.rows && layout.cols === p.cols) ? '#2563eb' : '#4b5563',
                                        border: '1px solid',
                                        borderColor: (layout.rows === p.rows && layout.cols === p.cols) ? '#2563eb' : '#d1d5db'
                                    }}
                                    title={`${p.rows} Rows x ${p.cols} Cols`}
                                >
                                    {p.label}
                                </button>
                            ))}
                        </div>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                        <label style={{ fontSize: '0.75rem', fontWeight: 600, color: '#6b7280' }}>
                            GAP
                        </label>
                        <input
                            type="range"
                            min="0"
                            max="50"
                            value={gap}
                            onChange={(e) => setGap(parseInt(e.target.value))}
                            style={{ width: '60px' }}
                            title={`Gap: ${gap}px`}
                        />
                    </div>
                </div>

                <div style={{ display: 'flex', gap: '0.5rem', marginLeft: 'auto' }}>
                    {fileCount > 0 && (
                        <button
                            onClick={onClearAll}
                            style={{
                                padding: '0.75rem',
                                borderRadius: '0.5rem',
                                color: '#ef4444',
                                fontWeight: 600,
                                border: '1px solid #fee2e2',
                                backgroundColor: '#fef2f2'
                            }}
                            title="Clear All Pages"
                        >
                            <Trash2 size={20} />
                        </button>
                    )}

                    <button
                        onClick={onPrint}
                        style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: '0.5rem',
                            backgroundColor: '#2563eb',
                            color: 'white',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '0.5rem',
                            fontWeight: 600,
                            boxShadow: '0 1px 2px 0 rgb(0 0 0 / 0.05)',
                        }}
                    >
                        <Printer size={20} />
                        Print
                    </button>
                </div>
            </div>
        </header>
    );
};
