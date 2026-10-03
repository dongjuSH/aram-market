// 상품 이미지·상세 편집기·관련 상품을 포함한 등록 및 수정 화면

import { useEffect, useRef, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import {
  createProduct,
  cleanupEditorImageDraft,
  deleteProduct,
  getProduct,
  getProductCategories,
  getRelatedCandidates,
  uploadEditorImage,
  updateProduct,
} from '../api/products.js'
import AdminHeader from '../components/products/admin-header.jsx'
import ProductEditor from '../components/products/product-editor.jsx'
import { ADMIN_LOGIN_PATH, ADMIN_PRODUCTS_PATH } from '../config/routes.js'


const MIN_PRODUCT_PRICE = 100
const MAX_PRODUCT_PRICE = 2_147_483_647

const EMPTY_FORM = {
  visible: true,
  displayOrder: '',
  categoryId: '',
  name: '',
  code: '',
  price: '',
  imageData: '',
  imageUrl: '',
  imageName: '',
  imageDescription: '',
  detailHtml: '',
  relatedProductIds: ['', ''],
}

function ChevronDownIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="m7 10 5 5 5-5" />
    </svg>
  )
}


function CalendarIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24">
      <path d="M7 3v3M17 3v3M4 9h16M5 5h14a1 1 0 0 1 1 1v14H4V6a1 1 0 0 1 1-1Z" />
    </svg>
  )
}


function ImagePlaceholderIcon() {
  return (
    <svg aria-hidden="true" viewBox="0 0 48 48">
      <rect x="7" y="8" width="34" height="32" rx="4" />
      <circle cx="18" cy="19" r="4" />
      <path d="m10 36 9-9 6 6 5-5 8 8" />
    </svg>
  )
}


// ISO 시각을 등록·수정 화면의 날짜만 표시
function formatDate(value) {
  if (!value) return ''
  return new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'Asia/Seoul',
  }).format(new Date(value))
}


// 달력 아이콘과 등록·수정 상태를 표시하는 상단 정보
function DateStatus({ label, value }) {
  return (
    <div className="product-date-status">
      <span>{label}</span>
      <strong><CalendarIcon />{value}</strong>
    </div>
  )
}


// 상품 등록·수정 데이터 로드, 검증 및 저장 작업 관리
function AdminProductFormPage({ mode, onNavigate }) {
  const isEdit = mode === 'edit'
  const productId = Number(new URLSearchParams(window.location.search).get('id'))
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('adminCurrentUser')) || {}
    } catch {
      return {}
    }
  })
  const [form, setForm] = useState(EMPTY_FORM)
  const [categories, setCategories] = useState([])
  const [relatedCandidates, setRelatedCandidates] = useState([])
  const [createdAt, setCreatedAt] = useState('')
  const [updatedAt, setUpdatedAt] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')
  const fileInputRef = useRef(null)
  const uploadSessionIdRef = useRef(crypto.randomUUID())
  const hasDraftUploadsRef = useRef(false)

  // 저장하지 않고 이동·새로고침·탭 종료 시 이 화면에서 올린 임시 상세 이미지만 정리
  useEffect(() => {
    const cleanupDraft = () => {
      if (!hasDraftUploadsRef.current) return
      hasDraftUploadsRef.current = false
      cleanupEditorImageDraft(uploadSessionIdRef.current, { keepalive: true }).catch(() => {})
    }
    window.addEventListener('pagehide', cleanupDraft)
    return () => {
      window.removeEventListener('pagehide', cleanupDraft)
      cleanupDraft()
    }
  }, [])

  // 인증 확인 후 카테고리와 수정 대상 상품 로드
  useEffect(() => {
    if (isEdit && (!Number.isInteger(productId) || productId < 1)) {
      onNavigate(ADMIN_PRODUCTS_PATH, { replace: true })
      return undefined
    }
    let isMounted = true
    Promise.all([getCurrentUser(), getProductCategories(), isEdit ? getProduct(productId) : Promise.resolve(null)])
      .then(([userResult, categoryResult, productResult]) => {
        if (!isMounted) return
        setUser(userResult.user)
        sessionStorage.setItem('adminCurrentUser', JSON.stringify(userResult.user))
        setCategories(categoryResult.categories)
        if (productResult) {
          const product = productResult.product
          setForm({
            visible: product.visible,
            displayOrder: String(product.display_order),
            categoryId: String(product.category_id),
            name: product.name,
            code: product.code,
            price: String(product.price),
            imageData: '',
            imageUrl: product.image_url,
            imageName: product.image_name,
            imageDescription: product.image_description,
            detailHtml: product.detail_html,
            relatedProductIds: [String(product.related_product_ids[0] || ''), String(product.related_product_ids[1] || '')],
          })
          setCreatedAt(product.created_at)
          setUpdatedAt(product.updated_at)
          setRelatedCandidates(productResult.related_candidates)
        }
      })
      .catch((requestError) => {
        if (!isMounted) return
        if (requestError.status === 401) {
          sessionStorage.removeItem('adminCurrentUser')
          onNavigate(ADMIN_LOGIN_PATH, { replace: true })
          return
        }
        setError(requestError.message)
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [isEdit, onNavigate, productId])

  // 카테고리 변경 시 같은 카테고리의 관련 상품 후보 갱신
  const changeCategory = async (categoryId) => {
    setForm((current) => ({ ...current, categoryId, relatedProductIds: ['', ''] }))
    setRelatedCandidates([])
    if (!categoryId) return
    try {
      const result = await getRelatedCandidates(Number(categoryId), isEdit ? productId : undefined)
      setRelatedCandidates(result.items)
    } catch (requestError) {
      setError(requestError.message)
    }
  }

  // JPG·PNG·GIF와 5MB 제한 확인 후 미리보기용 data URL 생성
  const selectImage = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!['image/jpeg', 'image/png', 'image/gif'].includes(file.type)) {
      setError('JPG, JPEG, PNG, GIF 이미지만 등록할 수 있습니다.')
      event.target.value = ''
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      setError('이미지 파일은 5MB 이하만 등록할 수 있습니다.')
      event.target.value = ''
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setForm((current) => ({ ...current, imageData: String(reader.result), imageUrl: String(reader.result), imageName: file.name }))
      setError('')
    }
    reader.readAsDataURL(file)
  }

  const updateRelated = (index, value) => {
    setForm((current) => {
      const next = [...current.relatedProductIds]
      next[index] = value
      return { ...current, relatedProductIds: next }
    })
  }

  // 필수값과 관련 상품 중복을 확인하고 API 입력 형식으로 변환
  const buildPayload = () => {
    if (!form.displayOrder || Number(form.displayOrder) < 1) throw new Error('노출순서는 1 이상의 숫자로 입력해 주세요.')
    if (!form.categoryId) throw new Error('카테고리를 선택해 주세요.')
    if (!form.name.trim()) throw new Error('상품명을 입력해 주세요.')
    if (!form.code.trim()) throw new Error('상품코드를 입력해 주세요.')
    const price = Number(form.price)
    if (!Number.isInteger(price) || price < MIN_PRODUCT_PRICE || price > MAX_PRODUCT_PRICE) {
      throw new Error(`가격을 ${MIN_PRODUCT_PRICE.toLocaleString('ko-KR')}원 이상 ${MAX_PRODUCT_PRICE.toLocaleString('ko-KR')}원 이하의 정수로 입력해 주세요.`)
    }
    if (!form.imageData && !form.imageUrl) throw new Error('상품 이미지를 첨부해 주세요.')
    const relatedIds = form.relatedProductIds.filter(Boolean).map(Number)
    if (new Set(relatedIds).size !== relatedIds.length) throw new Error('같은 관련 상품을 중복 선택할 수 없습니다.')
    return {
      visible: form.visible,
      display_order: Number(form.displayOrder),
      category_id: Number(form.categoryId),
      name: form.name.trim(),
      code: form.code.trim(),
      price,
      image_data: form.imageData || null,
      image_name: form.imageName,
      image_description: form.imageDescription.trim() || null,
      detail_html: form.detailHtml,
      related_product_ids: relatedIds,
      editor_upload_session_id: uploadSessionIdRef.current,
    }
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    let payload
    try {
      payload = buildPayload()
    } catch (validationError) {
      setError(validationError.message)
      return
    }
    setIsSubmitting(true)
    try {
      if (isEdit) await updateProduct(productId, payload)
      else await createProduct(payload)
      hasDraftUploadsRef.current = false
      onNavigate(ADMIN_PRODUCTS_PATH)
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setIsSubmitting(false)
    }
  }

  const remove = async () => {
    if (!window.confirm('상품을 삭제하시겠습니까? 삭제한 상품은 목록과 판매 화면에서 보이지 않습니다.')) return
    setIsSubmitting(true)
    setError('')
    try {
      await deleteProduct(productId)
      onNavigate(ADMIN_PRODUCTS_PATH)
    } catch (requestError) {
      setError(requestError.message)
      setIsSubmitting(false)
    }
  }

  const cancel = async () => {
    if (hasDraftUploadsRef.current) {
      hasDraftUploadsRef.current = false
      try {
        await cleanupEditorImageDraft(uploadSessionIdRef.current)
      } catch {
        // 정리 실패는 화면 이동을 막지 않으며 서버 로그와 후속 정리 대상으로 남긴다.
      }
    }
    onNavigate(ADMIN_PRODUCTS_PATH)
  }

  const hasUpdateHistory = createdAt && updatedAt && Math.abs(new Date(updatedAt) - new Date(createdAt)) >= 1000

  if (isLoading) {
    return <main className="products-page products-page--loading"><p>상품 정보를 불러오고 있습니다.</p></main>
  }

  return (
    <main className="products-page">
      <AdminHeader user={user} onNavigate={onNavigate} />
      <section className="product-form-content" aria-labelledby="product-form-title">
        <div className="product-form-heading">
          <div>
            <button className="product-form-back" type="button" onClick={() => onNavigate(ADMIN_PRODUCTS_PATH)}>← 상품 목록</button>
            <h1 id="product-form-title">상품 {isEdit ? '수정' : '등록'}</h1>
          </div>
        </div>

        <form className="product-form" onSubmit={submit}>
          <div className="product-date-row">
            <DateStatus label="등록일" value={isEdit ? formatDate(createdAt) : '최초 등록 중'} />
            <DateStatus label="수정일" value={hasUpdateHistory ? formatDate(updatedAt) : '수정 이력 없음'} />
          </div>

          <fieldset className="product-visibility">
            <legend>노출여부</legend>
            <label><input type="radio" name="visible" checked={form.visible} onChange={() => setForm({ ...form, visible: true })} /> 노출</label>
            <label><input type="radio" name="visible" checked={!form.visible} onChange={() => setForm({ ...form, visible: false })} /> 미노출</label>
          </fieldset>

          <label className="product-form-field">
            <span>노출순서 <b>*</b></span>
            <input type="number" min="1" step="1" value={form.displayOrder} onChange={(event) => setForm({ ...form, displayOrder: event.target.value })} placeholder="숫자만 입력 가능합니다." />
            <small>숫자가 낮을수록 실제 상품 페이지의 상위에 노출됩니다.</small>
          </label>

          <label className="product-form-field product-form-field--half">
            <span>카테고리 <b>*</b></span>
            <span className="product-select-control">
              <select value={form.categoryId} onChange={(event) => changeCategory(event.target.value)}>
                <option value="">선택해 주세요.</option>
                {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
              </select>
              <ChevronDownIcon />
            </span>
          </label>

          <label className="product-form-field">
            <span>상품명 <b>*</b></span>
            <div className="product-input-count">
              <input maxLength="50" value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
              <small>{form.name.length}/50자</small>
            </div>
          </label>

          <label className="product-form-field">
            <span>상품코드 <b>*</b></span>
            <input maxLength="50" value={form.code} onChange={(event) => setForm({ ...form, code: event.target.value })} />
          </label>

          <label className="product-form-field">
            <span>가격 <b>*</b></span>
            <input type="number" min={MIN_PRODUCT_PRICE} max={MAX_PRODUCT_PRICE} step="1" value={form.price} onChange={(event) => setForm({ ...form, price: event.target.value })} placeholder="숫자만 입력 가능합니다." />
          </label>

          <div className="product-form-field">
            <span>이미지 <b>*</b></span>
            <div className="product-image-upload">
              <div className="product-image-preview">
                {form.imageUrl ? <img src={form.imageUrl} alt={form.imageDescription || '상품 이미지 미리보기'} /> : <ImagePlaceholderIcon />}
              </div>
              <div>
                <p>· JPG, JPEG, PNG, GIF 허용<br />· 파일 용량 5MB 제한</p>
                <button type="button" onClick={() => fileInputRef.current?.click()}>파일 첨부</button>
                {form.imageName && <small>{form.imageName}</small>}
              </div>
              <input ref={fileInputRef} className="sr-only" type="file" accept=".jpg,.jpeg,.png,.gif,image/jpeg,image/png,image/gif" onChange={selectImage} />
            </div>
          </div>

          <label className="product-form-field">
            <span>이미지 설명</span>
            <div className="product-input-count">
              <input maxLength="200" value={form.imageDescription} onChange={(event) => setForm({ ...form, imageDescription: event.target.value })} />
              <small>{form.imageDescription.length}/200자</small>
            </div>
          </label>

          <div className="product-form-field">
            <span>상품 상세내용</span>
            <ProductEditor
              value={form.detailHtml}
              onChange={(detailHtml) => setForm((current) => ({ ...current, detailHtml }))}
              onUploadImage={(imageData) => {
                if (!form.categoryId) throw new Error('상세 이미지를 첨부하기 전에 카테고리를 선택해 주세요.')
                return uploadEditorImage(
                  imageData,
                  Number(form.categoryId),
                  uploadSessionIdRef.current,
                  isEdit ? productId : undefined,
                ).then((result) => {
                  hasDraftUploadsRef.current = true
                  return result
                })
              }}
              onError={setError}
            />
          </div>

          <div className="product-form-field">
            <span>관련상품</span>
            {form.categoryId && relatedCandidates.length === 0 ? (
              <p className="related-products-empty">같은 카테고리에 등록된 다른 상품이 없습니다.</p>
            ) : (
              <div className="related-products">
                {[0, 1].map((index) => (
                  <span className="product-select-control" key={index}>
                    <select value={form.relatedProductIds[index]} onChange={(event) => updateRelated(index, event.target.value)} disabled={!form.categoryId}>
                      <option value="">없음</option>
                      {relatedCandidates
                        .filter((candidate) => String(candidate.id) === form.relatedProductIds[index] || !form.relatedProductIds.includes(String(candidate.id)))
                        .map((candidate) => <option key={candidate.id} value={candidate.id}>{candidate.name} ({candidate.code})</option>)}
                    </select>
                    <ChevronDownIcon />
                  </span>
                ))}
              </div>
            )}
            <small>같은 카테고리 내 상품을 최대 2개까지 선택할 수 있습니다.</small>
          </div>

          {error && <p className="product-form-error" role="alert">{error}</p>}
          <div className="product-form-actions">
            {isEdit && <button className="product-delete-button" type="button" disabled={isSubmitting} onClick={remove}>삭제</button>}
            <button className="product-cancel-button" type="button" disabled={isSubmitting} onClick={cancel}>취소</button>
            <button className="product-save-button" type="submit" disabled={isSubmitting}>{isSubmitting ? '저장 중...' : isEdit ? '수정' : '등록'}</button>
          </div>
        </form>
      </section>
    </main>
  )
}

export default AdminProductFormPage
