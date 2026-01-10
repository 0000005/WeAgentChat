<script setup lang="ts">
import { ref } from 'vue'
import { Cropper } from 'vue-advanced-cropper'
import 'vue-advanced-cropper/dist/style.css'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Upload, Check, Image as ImageIcon, ExternalLink, Loader2 } from 'lucide-vue-next'
import { useToast } from '@/composables/useToast'
import { uploadImage } from '@/api/upload' // We need to create this API helper

const props = defineProps<{
  initialImage?: string
  title?: string
}>()

const emit = defineEmits<{
  (e: 'update:image', url: string): void
  (e: 'close'): void
}>()

const toast = useToast()
const fileInput = ref<HTMLInputElement | null>(null)
const selectedImage = ref<string | null>(null)
const isOpen = ref(true)
const isUploading = ref(false)
const cropperRef = ref<any>(null)

// If initial image exists, start with it? No, usually this is a "Change Avatar" dialog.
// But we might want to let them see current one.
// For now, assume this dialog opens when they want to upload/change.

const handleFileSelect = (event: Event) => {
  const file = (event.target as HTMLInputElement).files?.[0]
  if (!file) return

  // Validate type
  if (!file.type.startsWith('image/')) {
    toast.error('请选择图片文件')
    return
  }

  // Validate size (client side check, e.g. 5MB strict)
  if (file.size > 5 * 1024 * 1024) {
    toast.error('图片大小不能超过 5MB')
    return
  }

  const reader = new FileReader()
  reader.onload = (e) => {
    selectedImage.value = e.target?.result as string
  }
  reader.readAsDataURL(file)
  
  // Reset input value to allow re-selecting same file
  if (fileInput.value) fileInput.value.value = '' 
}

const triggerFileSelect = () => {
  fileInput.value?.click()
}

const handleConfirm = async () => {
  if (!cropperRef.value) return

  const { canvas } = cropperRef.value.getResult()
  if (!canvas) return

  isUploading.value = true
  try {
    // Convert canvas to blob
    const blob = await new Promise<Blob | null>(resolve => 
      canvas.toBlob((b: Blob | null) => resolve(b), 'image/jpeg', 0.8)
    )
    
    if (!blob) throw new Error('Failed to crop image')

    const formData = new FormData()
    formData.append('file', blob, 'avatar.jpg')

    const response = await uploadImage(formData)
    emit('update:image', response.url)
    isOpen.value = false
    emit('close')
    toast.success('头像上传成功')
  } catch (error: any) {
    console.error(error)
    toast.error(error.message || '上传失败')
  } finally {
    isUploading.value = false
  }
}

const handleClose = () => {
  isOpen.value = false
  emit('close')
}

// Avataaars generator link
const AVATAAARS_URL = 'https://getavataaars.com/'
</script>

<template>
  <Dialog :open="isOpen" @update:open="handleClose">
    <DialogContent class="sm:max-w-[500px] p-0 overflow-hidden bg-white">
      <DialogHeader class="px-6 py-4 border-b">
        <DialogTitle>{{ title || '上传头像' }}</DialogTitle>
      </DialogHeader>

      <div class="p-6 flex flex-col items-center gap-6">
        <!-- Cropper Area / Preview -->
        <div class="w-[300px] h-[300px] bg-gray-100 rounded-lg overflow-hidden flex items-center justify-center border-2 border-dashed border-gray-200">
          <Cropper
            v-if="selectedImage"
            ref="cropperRef"
            class="upload-cropper"
            :src="selectedImage"
            :stencil-props="{ aspectRatio: 1/1 }"
            :resize-image="{ adjustStencil: false }"
            image-restriction="stencil"
          />
          
          <div v-else class="text-center text-gray-400 p-4">
            <ImageIcon class="w-12 h-12 mx-auto mb-2 opacity-50" />
            <p class="text-sm">支持 JPG, PNG, WEBP</p>
            <p class="text-xs mt-1">建议尺寸 200x200 以上</p>
          </div>
        </div>

        <!-- Hidden input -->
        <input 
          ref="fileInput"
          type="file" 
          accept="image/png, image/jpeg, image/webp" 
          class="hidden" 
          @change="handleFileSelect"
        />

        <!-- Actions -->
        <div class="w-full flex justify-center gap-3">
          <Button v-if="!selectedImage" variant="outline" @click="triggerFileSelect">
            <Upload class="w-4 h-4 mr-2" />
            选择本地图片
          </Button>
          <Button v-if="selectedImage" variant="outline" @click="triggerFileSelect">
            <Upload class="w-4 h-4 mr-2" />
            更换图片
          </Button>
           <a v-if="!selectedImage" :href="AVATAAARS_URL" target="_blank" class="no-underline">
             <Button variant="ghost" class="text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50">
                <ExternalLink class="w-4 h-4 mr-2" />
                去生成卡通头像
             </Button>
           </a>
        </div>
      </div>

      <DialogFooter class="px-6 py-4 bg-gray-50 flex justify-between items-center">
         <Button variant="ghost" @click="handleClose" :disabled="isUploading">取消</Button>
         <Button @click="handleConfirm" :disabled="!selectedImage || isUploading" class="bg-emerald-600 hover:bg-emerald-700">
            <Loader2 v-if="isUploading" class="w-4 h-4 mr-2 animate-spin" />
            <Check v-else class="w-4 h-4 mr-2" />
            确定上传
         </Button>
      </DialogFooter>
    </DialogContent>
  </Dialog>
</template>

<style scoped>
.upload-cropper {
  width: 100%;
  height: 100%;
  background: #DDD;
}
</style>
