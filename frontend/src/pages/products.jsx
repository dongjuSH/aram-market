// 고객이 로그인 없이 노출 상품을 검색·카테고리·페이지 단위로 조회하는 페이지

import { useEffect, useState } from 'react'
import { getCatalogCategories, getCatalogProducts } from '../api/products.js'
import CatalogFooter from '../components/products/catalog-footer.jsx'
import CatalogHeader from '../components/products/catalog-header.jsx'
import { getCustomerProductDetailPath } from '../config/routes.js'


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
  const [isCompactCatalog, setIsCompactCatalog] = useState(() => window.matchMedia('(max-width: 880px)').matches)
  const pageSize = isCompactCatalog ? 8 : 12

  useEffect(() => {
    const mediaQuery = window.matchMedia('(max-width: 880px)')
    const handleChange = (event) => {
      setIsLoading(true)
      setPage(1)
      setIsCompactCatalog(event.matches)
    }
    mediaQuery.addEventListener('change', handleChange)
    return () => mediaQuery.removeEventListener('change', handleChange)
  }, [])

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
  }, [categoryId, keyword, page, pageSize])

  const totalPages = Math.max(1, Math.ceil(total / pageSize))

  return (
    <div className="catalog-page">
      <a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a>
      <CatalogHeader
        onNavigate={onNavigate}
        searchValue={keywordInput}
        onSearchValueChange={(event) => setKeywordInput(event.target.value)}
        onSearch={(event) => {
          event.preventDefault()
          setIsLoading(true)
          setPage(1)
          setKeyword(keywordInput.trim())
        }}
      />

      <main id="catalog-main" tabIndex="-1">
        <section className="catalog-hero" aria-labelledby="catalog-hero-title">
        <div className="catalog-hero__content">
          <p className="catalog-hero__eyebrow">BETTER GOODS, BETTER DAYS</p>
          <h1 id="catalog-hero-title">좋은 상품으로<br />일상을 더 다정하게</h1>
          <p>생활에 꼭 필요한 상품을 한곳에서 만나보세요.</p>
        </div>
        </section>

        <nav className="catalog-categories" aria-label="상품 카테고리">
        <button
          className={!categoryId ? 'is-active' : ''}
          type="button"
          aria-pressed={!categoryId}
          onClick={() => {
            setIsLoading(true)
            setCategoryId('')
            setPage(1)
          }}
        >
          전체
        </button>
        {categories.map((category) => (
          <button
            className={String(category.id) === categoryId ? 'is-active' : ''}
            key={category.id}
            type="button"
            aria-pressed={String(category.id) === categoryId}
            onClick={() => {
              setIsLoading(true)
              setCategoryId(String(category.id))
              setPage(1)
            }}
          >
            {category.name}
          </button>
        ))}
        </nav>

        <div className="catalog-results-heading" aria-live="polite">
        <div>
          <p>OUR PRODUCTS</p>
          <h2>{categoryId ? categories.find((category) => String(category.id) === categoryId)?.name : '전체 상품'}</h2>
        </div>
        {!isLoading && !error && <span>총 {total.toLocaleString('ko-KR')}개</span>}
        </div>

        {error && <p className="catalog-notice catalog-notice--error" role="alert">{error}</p>}
        {isLoading ? (
          <p className="catalog-notice" role="status">상품을 불러오고 있습니다.</p>
        ) : (
          <section className="catalog-grid" aria-label="상품 목록">
          {products.map((product) => (
            <button
              className="catalog-card"
              key={product.id}
              type="button"
              onClick={() => onNavigate(getCustomerProductDetailPath(product.id))}
            >
              {product.image_url ? (
                <img src={product.image_url} alt={product.image_description || product.name} />
              ) : (
                <span className="catalog-card__placeholder" aria-hidden="true">NO IMAGE</span>
              )}
              <span className="catalog-card__category">{product.category}</span>
              <strong>{product.name}</strong>
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

      <CatalogFooter />
    </div>
  )
}

export default ProductsPage
