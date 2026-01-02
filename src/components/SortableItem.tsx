import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';

interface SortableItemProps {
    id: string;
    className?: string; // Add className prop
    children: React.ReactNode;
}

export const SortableItem: React.FC<SortableItemProps> = ({ id, className, children }) => {
    const {
        attributes,
        listeners,
        setNodeRef,
        transform,
        transition,
        isDragging
    } = useSortable({ id });

    const style = {
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
        height: '100%',
        width: '100%',
        touchAction: 'none' // Important for mobile D&D
    };

    return (
        <div ref={setNodeRef} style={style} className={className} {...attributes} {...listeners}>
            {children}
        </div>
    );
};
