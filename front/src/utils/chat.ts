export const INITIAL_MESSAGE_LIMIT = 10 // TODO: Change back to 30 after testing

/**
 * Parse message content into segments based on <message> tags.
 * If no tags are found, returns original content as a single segment.
 *
 * Edge cases handled:
 * 1. No tags at all → return original content as single segment
 * 2. Multiple complete <message>...</message> tags → return all segments
 * 3. Trailing unclosed <message>... → include as last segment (for SSE streaming)
 * 4. Empty <message></message> → filter out
 * 5. Malformed/nested tags → extract outermost complete blocks
 */
export function parseMessageSegments(content: string): string[] {
    if (!content) return []

    // Quick path: no tags at all
    if (!content.includes('<message>')) {
        return [content.trim()]
    }

    const regex = /<message>([\s\S]*?)<\/message>/g
    const segments: string[] = []
    let lastIndex = 0
    let match

    while ((match = regex.exec(content)) !== null) {
        const segment = match[1].trim()
        if (segment) {
            segments.push(segment)
        }
        lastIndex = regex.lastIndex
    }

    // Handle trailing unclosed <message> tag (SSE streaming case)
    const remainingContent = content.slice(lastIndex)
    if (remainingContent.includes('<message>')) {
        const openTagIndex = remainingContent.indexOf('<message>')
        const trailingContent = remainingContent.slice(openTagIndex + '<message>'.length).trim()
        if (trailingContent) {
            segments.push(trailingContent)
        }
    }

    // Fallback: if we found <message> tags but extracted nothing, show raw content
    if (segments.length === 0) {
        return [content.trim()]
    }

    return segments
}
