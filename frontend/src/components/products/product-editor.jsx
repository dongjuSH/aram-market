// Tiptap 기반 상품 상세내용 서식·링크·Storage 이미지 편집기

import { useEffect, useRef, useState } from 'react'
import Image from '@tiptap/extension-image'
import { EditorContent, useEditor } from '@tiptap/react'
import StarterKit from '@tiptap/starter-kit'


// 디자인 툴바용 공통 명령 버튼
function ToolbarButton({ label, active = false, disabled = false, onClick, children }) {
  return (
    <button
      className={active ? 'is-active' : ''}
      type="button"
      aria-label={label}
      aria-pressed={active}
      disabled={disabled}
      onClick={onClick}
    >
      {children}
    </button>
  )
}


function ChevronDownIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m7 10 5 5 5-5" />
    </svg>
  )
}


// 첨부 시안의 주요 서식 기능을 제공하는 본문 에디터
function ProductEditor({ value, onChange, onUploadImage, onError }) {
  const [isUploading, setIsUploading] = useState(false)
  const fileInputRef = useRef(null)
  const editor = useEditor({
    extensions: [
      StarterKit.configure({
        heading: { levels: [1, 2, 3] },
        link: { openOnClick: false, autolink: true, defaultProtocol: 'https' },
      }),
      Image.configure({ allowBase64: false, inline: false }),
    ],
    content: value,
    editorProps: {
      attributes: {
        class: 'product-editor__content',
        'aria-label': '상품 상세내용',
      },
    },
    onUpdate: ({ editor: currentEditor }) => onChange(currentEditor.getHTML()),
  })

  useEffect(() => {
    if (!editor || editor.isDestroyed || !editor.schema) return
    if (value !== editor.getHTML()) editor.commands.setContent(value, { emitUpdate: false })
  }, [editor, value])

  const setHeading = (event) => {
    const level = Number(event.target.value)
    if (level) editor.chain().focus().setHeading({ level }).run()
    else editor.chain().focus().setParagraph().run()
  }

  const setLink = () => {
    const previousUrl = editor.getAttributes('link').href || ''
    const url = window.prompt('연결할 주소를 입력해 주세요.', previousUrl)
    if (url === null) return
    if (!url.trim()) {
      editor.chain().focus().extendMarkRange('link').unsetLink().run()
      return
    }
    const normalizedUrl = url.trim()
    if (!normalizedUrl.startsWith('http://') && !normalizedUrl.startsWith('https://') && !normalizedUrl.startsWith('mailto:')) {
      onError('링크는 http://, https:// 또는 mailto: 주소만 사용할 수 있습니다.')
      return
    }
    editor.chain().focus().extendMarkRange('link').setLink({ href: normalizedUrl }).run()
  }

  const uploadImage = async (event) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/gif'].includes(file.type) || file.size > 5 * 1024 * 1024) {
      onError('JPG, JPEG, PNG, GIF 형식의 5MB 이하 이미지만 삽입할 수 있습니다.')
      return
    }
    setIsUploading(true)
    try {
      const imageData = await new Promise((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = () => resolve(String(reader.result))
        reader.onerror = reject
        reader.readAsDataURL(file)
      })
      const result = await onUploadImage(imageData)
      editor.chain().focus().setImage({ src: result.url, alt: file.name }).run()
    } catch (error) {
      onError(error.message || '에디터 이미지를 업로드하지 못했습니다.')
    } finally {
      setIsUploading(false)
    }
  }

  if (!editor || editor.isDestroyed || !editor.schema) return <div className="product-editor product-editor--loading">에디터를 준비하고 있습니다.</div>

  const headingValue = [1, 2, 3].find((level) => editor.isActive('heading', { level })) || 0

  return (
    <div className="product-editor">
      <div className="product-editor__toolbar" role="toolbar" aria-label="상품 상세내용 서식">
        <span className="product-editor__select">
          <select aria-label="제목 서식" value={headingValue} onChange={setHeading}>
            <option value="0">본문</option>
            <option value="1">Heading 1</option>
            <option value="2">Heading 2</option>
            <option value="3">Heading 3</option>
          </select>
          <ChevronDownIcon />
        </span>
        <span className="product-editor__divider" />
        <ToolbarButton label="굵게" active={editor.isActive('bold')} onClick={() => editor.chain().focus().toggleBold().run()}><strong>B</strong></ToolbarButton>
        <ToolbarButton label="기울임" active={editor.isActive('italic')} onClick={() => editor.chain().focus().toggleItalic().run()}><em>I</em></ToolbarButton>
        <ToolbarButton label="밑줄" active={editor.isActive('underline')} onClick={() => editor.chain().focus().toggleUnderline().run()}><u>U</u></ToolbarButton>
        <ToolbarButton label="취소선" active={editor.isActive('strike')} onClick={() => editor.chain().focus().toggleStrike().run()}><s>S</s></ToolbarButton>
        <ToolbarButton label="인용" active={editor.isActive('blockquote')} onClick={() => editor.chain().focus().toggleBlockquote().run()}>❞</ToolbarButton>
        <ToolbarButton label="링크" active={editor.isActive('link')} onClick={setLink}>↗</ToolbarButton>
        <ToolbarButton label="이미지 삽입" disabled={isUploading} onClick={() => fileInputRef.current?.click()}>{isUploading ? '…' : '▣'}</ToolbarButton>
        <ToolbarButton label="글머리 목록" active={editor.isActive('bulletList')} onClick={() => editor.chain().focus().toggleBulletList().run()}>☷</ToolbarButton>
        <ToolbarButton label="번호 목록" active={editor.isActive('orderedList')} onClick={() => editor.chain().focus().toggleOrderedList().run()}>≣</ToolbarButton>
        <ToolbarButton label="구분선" onClick={() => editor.chain().focus().setHorizontalRule().run()}>―</ToolbarButton>
        <ToolbarButton label="실행 취소" disabled={!editor.can().undo()} onClick={() => editor.chain().focus().undo().run()}>↶</ToolbarButton>
        <ToolbarButton label="다시 실행" disabled={!editor.can().redo()} onClick={() => editor.chain().focus().redo().run()}>↷</ToolbarButton>
        <input ref={fileInputRef} className="sr-only" type="file" accept=".jpg,.jpeg,.png,.gif,image/jpeg,image/png,image/gif" onChange={uploadImage} />
      </div>
      <EditorContent editor={editor} />
    </div>
  )
}

export default ProductEditor
