import { getApiBaseUrl } from './base'

export interface UploadResponse {
    url: string
}

export async function uploadImage(formData: FormData): Promise<UploadResponse> {
    const baseUrl = getApiBaseUrl()
    // Assuming API prefix is /api, which is standard in this project
    const url = `${baseUrl}/api/upload/image`

    const response = await fetch(url, {
        method: 'POST',
        body: formData,
    })

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(error.detail || 'Image upload failed')
    }

    // Return the relative URL (e.g. /uploads/avatars/...)
    // The frontend might need to prepend base URL if it's strictly local file serving, 
    // but usually <img src="/uploads/..." /> works if frontend proxy handles it, 
    // OR we need full URL if backend is on different port and no proxy.
    // For Electron/Dev with different ports, we need full URL or base.

    const data = await response.json()
    // data.url is relative e.g. /uploads/avatars/xyz.png

    // We should probably return the full URL for the frontend to display easily?
    // Or let the component handle it. 
    // Actually, storing relative path is better for DB portable.
    // But displaying requires full URL.

    return data
}
