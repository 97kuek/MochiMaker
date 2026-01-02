import React, { useEffect, useRef } from 'react';

export const CanvasPreview: React.FC<{ canvas: HTMLCanvasElement }> = ({ canvas }) => {
    const containerRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        if (containerRef.current) {
            containerRef.current.innerHTML = '';
            canvas.style.width = '100%';
            canvas.style.height = '100%';
            canvas.style.objectFit = 'contain';
            containerRef.current.appendChild(canvas);
        }
    }, [canvas]);

    return <div ref={containerRef} style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }} />;
};
