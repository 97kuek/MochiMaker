import React from 'react';

interface GridPageProps {
    items: React.ReactNode[];
    columns: number;
    gap: number;
    pageIndex: number;
}

export const GridPage: React.FC<GridPageProps> = ({ items, columns, gap, pageIndex }) => {


    // We use CSS Grid for layout
    const gridStyle: React.CSSProperties = {
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, 1fr)`,
        // We can also set rows dynamically or just let them flow.
        // For a strict N-up layout, usually rows are also defined to fit exactly on page,
        // but allowing auto-flow is safer for variable aspect ratios.
        // Let's try to enforce a grid that fills the height if possible, or just standard flow.
        // Standard flow is safer for 2024.
        gap: `${gap}px`,
    };

    return (
        <div className="a4-page">
            <div style={{ ...gridStyle, height: '100%' }}>
                {items.map((item, idx) => (
                    <div key={idx} className="grid-item">
                        {item}
                    </div>
                ))}
            </div>

            {/* Page Number (optional, good for verification) */}
            <div style={{
                position: 'absolute',
                bottom: '5mm',
                right: '10mm',
                fontSize: '10px',
                color: '#ccc',
                pointerEvents: 'none'
            }}>
                Page {pageIndex + 1}
            </div>
        </div>
    );
};
