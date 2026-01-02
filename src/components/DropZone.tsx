import React, { useCallback, useState } from 'react';
import { Upload, FileText } from 'lucide-react';

interface DropZoneProps {
    onFilesSelect: (files: File[]) => void;
}

export const DropZone: React.FC<DropZoneProps> = ({ onFilesSelect }) => {
    const [isDragging, setIsDragging] = useState(false);

    const handleDragOver = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(true);
    }, []);

    const handleDragLeave = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);
    }, []);

    const handleDrop = useCallback((e: React.DragEvent) => {
        e.preventDefault();
        setIsDragging(false);

        const droppedFiles = Array.from(e.dataTransfer.files);
        const pdfFiles = droppedFiles.filter(f => f.type === 'application/pdf');

        if (pdfFiles.length > 0) {
            onFilesSelect(pdfFiles);
        } else {
            alert('Please upload PDF files.');
        }
    }, [onFilesSelect]);

    const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
        if (e.target.files && e.target.files.length > 0) {
            const selectedFiles = Array.from(e.target.files);
            onFilesSelect(selectedFiles);
        }
    }, [onFilesSelect]);

    return (
        <div
            className={`dropzone ${isDragging ? 'active' : ''}`}
            onDragOver={handleDragOver}
            onDragLeave={handleDragLeave}
            onDrop={handleDrop}
        >
            <input
                type="file"
                id="file-upload"
                accept="application/pdf"
                multiple
                style={{ display: 'none' }}
                onChange={handleFileInput}
            />

            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '1rem' }}>
                <div style={{
                    backgroundColor: isDragging ? '#dbeafe' : '#f3f4f6',
                    padding: '1rem',
                    borderRadius: '50%'
                }}>
                    {isDragging ? <FileText size={48} className="text-blue-500" /> : <Upload size={48} className="text-gray-400" />}
                </div>

                <div>
                    <h3 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                        Upload Lecture PDFs
                    </h3>
                    <p style={{ color: '#6b7280', marginBottom: '1.5rem' }}>
                        Drag & drop multiple PDFs here, or click to browse
                    </p>

                    <label
                        htmlFor="file-upload"
                        style={{
                            backgroundColor: '#2563eb',
                            color: 'white',
                            padding: '0.75rem 1.5rem',
                            borderRadius: '0.5rem',
                            fontWeight: 500,
                            cursor: 'pointer',
                            display: 'inline-block'
                        }}
                    >
                        Select PDF Files
                    </label>
                </div>
            </div>
        </div>
    );
};
