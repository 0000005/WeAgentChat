export interface ExportMessage {
  id: string | number
  content: string
  isUser: boolean
  avatar: string
  name?: string
  showName?: boolean
}
