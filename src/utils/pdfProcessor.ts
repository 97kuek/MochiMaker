import * as pdfjsLib from 'pdfjs-dist';

// Set up the worker source. 
// Use local public file for offline support, ensuring correct path with base URL.
pdfjsLib.GlobalWorkerOptions.workerSrc = `${import.meta.env.BASE_URL}pdf.worker.min.mjs`;

export interface PDFPageData {
    id: string;
    pageNumber: number;
    canvas: HTMLCanvasElement;
    width: number;
    height: number;
}

export const loadPDF = async (file: File): Promise<pdfjsLib.PDFDocumentProxy> => {
    const arrayBuffer = await file.arrayBuffer();
    const loadingTask = pdfjsLib.getDocument({ data: arrayBuffer });
    return loadingTask.promise;
};

export const renderPageToCanvas = async (
    pdf: pdfjsLib.PDFDocumentProxy,
    pageNumber: number,
    scale = 2.0 // High resolution for print
): Promise<PDFPageData> => {
    const page = await pdf.getPage(pageNumber);
    const viewport = page.getViewport({ scale });

    const canvas = document.createElement('canvas');
    const context = canvas.getContext('2d');
    canvas.height = viewport.height;
    canvas.width = viewport.width;

    if (!context) {
        throw new Error('Could not get canvas context');
    }

    const renderContext = {
        canvasContext: context,
        viewport: viewport,
    };

    // @ts-ignore
    await page.render(renderContext).promise;

    return {
        id: crypto.randomUUID(),
        pageNumber,
        canvas,
        width: viewport.width,
        height: viewport.height,
    };
};
