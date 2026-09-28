// 고객이 로그인 없이 노출 상품을 검색·카테고리·페이지 단위로 조회하는 페이지

import { useEffect, useState } from 'react'
import { getCatalogCategories, getCatalogProducts } from '../api/products.js'


// 공개 상품 카탈로그 조회와 화면 상태 관리
function ProductsPage({ onNavigate }) {
  const [categories, setCategories] = useState([])
  const [products, setProducts] = useState([])
  const [keywordInput, setKeywordInput] = useState('')
  const [keyword, setKeyword] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const pageSize = 12

  useEffect(() => {
    getCatalogCategories()
      .then((result) => setCategories(result.categories))
      .catch((requestError) => setError(requestError.message))
  }, [])

  useEffect(() => {
    let isMounted = true
    getCatalogProducts({ keyword, categoryId, page, pageSize })
      .then((result) => {
        if (!isMounted) return
        setProducts(result.items)
        setTotal(result.total)
        setError('')
      })
      .catch((requestError) => {
        if (!isMounted) return
        setProducts([])
        setTotal(0)
        setError(requestError.message)
      })
      .finally(() => {
        if (isMounted) setIsLoading(false)
      })
    return () => {
      isMounted = false
    }
  }, [categoryId, keyword, page])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <main className="catalog-page">
      <header className="catalog-header">
        <div>
          <p className="catalog-eyebrow">PRODUCT CATALOG</p>
          <h1>상품</h1>
        </div>
      </header>

      <section className="catalog-hero">
        <p>관리자가 등록하고 공개한 상품을 확인할 수 있습니다.</p>
        <form
          className="catalog-filters"
          onSubmit={(event) => {
            event.preventDefault()
            setIsLoading(true)
            setPage(1)
            setKeyword(keywordInput.trim())
          }}
        >
          <input
            type="search"
            aria-label="상품 검색"
            placeholder="상품명 또는 상품코드 검색"
            value={keywordInput}
            onChange={(event) => setKeywordInput(event.target.value)}
          />
          <select
            aria-label="카테고리"
            value={categoryId}
            onChange={(event) => {
              setIsLoading(true)
              setCategoryId(event.target.value)
              setPage(1)
            }}
          >
            <option value="">전체 카테고리</option>
            {categories.map((category) => <option key={category.id} value={category.id}>{category.name}</option>)}
          </select>
          <button type="submit">검색</button>
        </form>
      </section>

      {error && <p className="catalog-notice catalog-notice--error" role="alert">{error}</p>}
      {isLoading ? (
        <p className="catalog-notice">상품을 불러오고 있습니다.</p>
      ) : (
        <section className="catalog-grid" aria-label="상품 목록">
          {products.map((product) => (
            <button
              className="catalog-card"
              key={product.id}
              type="button"
              onClick={() => onNavigate(`/products/detail?id=${product.id}`)}
            >
              {product.image_url ? (
                <img src={product.image_url} alt={product.image_description || product.name} />
              ) : (
                <span className="catalog-card__placeholder" aria-hidden="true">NO IMAGE</span>
              )}
              <span className="catalog-card__category">{product.category}</span>
              <strong>{product.name}</strong>
              <span className="catalog-card__code">{product.code}</span>
              <span className="catalog-card__price">{product.price.toLocaleString('ko-KR')}원</span>
            </button>
          ))}
          {!products.length && !error && <p className="catalog-empty">조건에 맞는 상품이 없습니다.</p>}
        </section>
      )}

      {totalPages > 1 && (
        <nav className="catalog-pagination" aria-label="상품 페이지">
          <button type="button" disabled={page <= 1} onClick={() => { setIsLoading(true); setPage((current) => current - 1) }}>이전</button>
          <span>{page} / {totalPages}</span>
          <button type="button" disabled={page >= totalPages} onClick={() => { setIsLoading(true); setPage((current) => current + 1) }}>다음</button>
        </nav>
      )}
    </main>
  )
}

export default ProductsPage
