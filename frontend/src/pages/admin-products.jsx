// 로그인 사용자별 상품 검색·페이지 이동 및 등록·수정 화면 진입

import { useEffect, useState } from 'react'
import { getCurrentUser } from '../api/auth.js'
import { getProducts, restoreProduct } from '../api/products.js'
import AdminHeader from '../components/products/admin-header.jsx'
import ProductPagination from '../components/products/product-pagination.jsx'
import ProductSearch from '../components/products/product-search.jsx'
import ProductTable from '../components/products/product-table.jsx'
import { ADMIN_LOGIN_PATH, ADMIN_PRODUCT_CREATE_PATH, ADMIN_PRODUCT_EDIT_PATH } from '../config/routes.js'

// 상품관리 UI 및 로그인 사용자 계정 메뉴 상태 관리
function AdminProductsPage({ onNavigate }) {
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(sessionStorage.getItem('adminCurrentUser')) || {}
    } catch {
      return {}
    }
  })
  const [isCheckingSession, setIsCheckingSession] = useState(true)
  const [products, setProducts] = useState([])
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)
  const [productStatus, setProductStatus] = useState('active')
  const [requestVersion, setRequestVersion] = useState(0)
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [restoringId, setRestoringId] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  // 상품 화면 진입 시 서버에서 토큰 유효성을 확인하고 만료 세션 차단
  useEffect(() => {
    let isMounted = true
    getCurrentUser()
      .then((result) => {
        if (!isMounted) return
        setUser(result.user)
        sessionStorage.setItem('adminCurrentUser', JSON.stringify(result.user))
      })
      .catch(() => {
        if (!isMounted) return
        sessionStorage.removeItem('adminAccessToken')
        sessionStorage.removeItem('adminCurrentUser')
        sessionStorage.setItem('adminAuthNotice', '로그인이 만료되었습니다. 다시 로그인해 주세요.')
        onNavigate(ADMIN_LOGIN_PATH, { replace: true })
      })
      .finally(() => {
        if (isMounted) setIsCheckingSession(false)
      })

    return () => {
      isMounted = false
    }
  }, [onNavigate])

  // 검색 조건 또는 페이지 변경 시 현재 사용자의 상품 조회
  useEffect(() => {
    if (isCheckingSession) return undefined
    let isMounted = true
    getProducts({ keyword, page, pageSize, status: productStatus })
      .then((result) => {
        if (!isMounted) return
        setError('')
        setProducts(result.items)
        setTotal(result.total)
        if (result.total > 0 && result.items.length === 0 && page > 1) setPage(Math.max(1, Math.ceil(result.total / pageSize)))
      })
      .catch((requestError) => {
        if (!isMounted) return
        if (requestError.status === 401) {
          sessionStorage.removeItem('adminAccessToken')
          onNavigate(ADMIN_LOGIN_PATH, { replace: true })
          return
        }
        setError(requestError.message)
        setProducts([])
        setTotal(0)
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [isCheckingSession, keyword, page, pageSize, productStatus, requestVersion, onNavigate])

  const search = (event) => {
    event.preventDefault()
    setIsLoading(true)
    setPage(1)
    setKeyword(keywordInput.trim())
    setRequestVersion((current) => current + 1)
  }

  const changeStatus = (nextStatus) => {
    setIsLoading(true)
    setProductStatus(nextStatus)
    setPage(1)
    setRequestVersion((current) => current + 1)
    setError('')
    setNotice('')
  }

  const restore = async (product) => {
    if (!window.confirm(`‘${product.name}’ 상품을 복원하시겠습니까? 복원 후에는 미노출 상태로 저장됩니다.`)) return
    setRestoringId(product.id)
    setError('')
    setNotice('')
    try {
      const result = await restoreProduct(product.id)
      setNotice(result.message)
      const refreshed = await getProducts({ keyword, page, pageSize, status: productStatus })
      setProducts(refreshed.items)
      setTotal(refreshed.total)
      if (refreshed.total > 0 && refreshed.items.length === 0 && page > 1) {
        setPage(Math.max(1, Math.ceil(refreshed.total / pageSize)))
      }
    } catch (requestError) {
      setError(requestError.message)
    } finally {
      setRestoringId(null)
    }
  }

  if (isCheckingSession) {
    return (
      <main className="products-page products-page--loading">
        <p>로그인 정보를 확인하고 있습니다.</p>
      </main>
    )
  }

  return (
    <main className="products-page">
      <AdminHeader user={user} onNavigate={onNavigate} />

      <section className="product-content" aria-labelledby="product-list-title">
        <div className="product-toolbar">
          <div>
            <h1 id="product-list-title">상품 목록</h1>
            <p>상품 정보와 노출 상태를 관리합니다.</p>
          </div>
          <ProductSearch
            keyword={keywordInput}
            pageSize={pageSize}
            onKeywordChange={setKeywordInput}
            onSearch={search}
            onPageSizeChange={(value) => {
              setIsLoading(true)
              setPageSize(value)
              setPage(1)
            }}
          />
        </div>
        <div className="product-status-tabs" role="tablist" aria-label="상품 상태">
          <button
            className={productStatus === 'active' ? 'is-active' : ''}
            type="button"
            role="tab"
            aria-selected={productStatus === 'active'}
            onClick={() => changeStatus('active')}
          >
            판매 상품
          </button>
          <button
            className={productStatus === 'deleted' ? 'is-active' : ''}
            type="button"
            role="tab"
            aria-selected={productStatus === 'deleted'}
            onClick={() => changeStatus('deleted')}
          >
            삭제된 상품
          </button>
        </div>
        {error && <p className="product-notice product-notice--error" role="alert">{error}</p>}
        {notice && <p className="product-notice product-notice--success" role="status">{notice}</p>}
        <ProductTable
          products={products}
          page={page}
          pageSize={pageSize}
          isLoading={isLoading}
          status={productStatus}
          restoringId={restoringId}
          onEdit={(productId) => onNavigate(`${ADMIN_PRODUCT_EDIT_PATH}?id=${productId}`)}
          onRestore={restore}
        />
        <ProductPagination
          page={page}
          total={total}
          pageSize={pageSize}
          onPageChange={(nextPage) => {
            if (nextPage === page) return
            setIsLoading(true)
            setPage(nextPage)
          }}
          onCreate={productStatus === 'active' ? () => onNavigate(ADMIN_PRODUCT_CREATE_PATH) : null}
        />
      </section>
    </main>
  )
}

export default AdminProductsPage
