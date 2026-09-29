// 고객이 로그인 없이 노출 상품을 검색·카테고리·페이지 단위로 조회하는 페이지

import { useEffect, useRef, useState } from 'react'
import { getCatalogCategories, getCatalogProducts } from '../api/products.js'
import CatalogFooter from '../components/products/catalog-footer.jsx'
import CatalogHeader from '../components/products/catalog-header.jsx'
import ProductCard from '../components/products/product-card.jsx'
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
  const headingRef = useRef(null)
  const gridRef = useRef(null)
  const shouldFocusListRef = useRef(false) // 페이지 이동으로 목록이 바뀐 뒤 첫 상품으로 포커스를 옮길지 여부

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

  // 페이지 이동 후 새 목록이 그려지면 목록 제목이 보이게 스크롤하고 첫 번째 상품으로 포커스 이동
  useEffect(() => {
    if (isLoading || !shouldFocusListRef.current) return
    shouldFocusListRef.current = false
    headingRef.current?.scrollIntoView({ block: 'start' })
    gridRef.current?.querySelector('.product-card__info')?.focus({ preventScroll: true })
  }, [isLoading, products])

  // 번호·이전·다음 버튼으로 페이지 이동
  const changePage = (nextPage) => {
    shouldFocusListRef.current = true
    setIsLoading(true)
    setPage(nextPage)
  }

  // 카테고리 메뉴는 검색어를 초기화하고 해당 카테고리 전체 상품을 보여줌
  const selectCategory = (nextCategoryId) => {
    setIsLoading(true)
    setKeywordInput('')
    setKeyword('')
    setCategoryId(nextCategoryId)
    setPage(1)
  }

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
          setCategoryId('') // 검색은 전체 상품에서 수행
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
          onClick={() => selectCategory('')}
        >
          전체
        </button>
        {categories.map((category) => (
          <button
            className={String(category.id) === categoryId ? 'is-active' : ''}
            key={category.id}
            type="button"
            aria-pressed={String(category.id) === categoryId}
            onClick={() => selectCategory(String(category.id))}
          >
            {category.name}
          </button>
        ))}
        </nav>

        <div className="catalog-results-heading" aria-live="polite" ref={headingRef}>
        <div>
          <p>{keyword ? 'SEARCH RESULTS' : 'OUR PRODUCTS'}</p>
          <h2>{keyword ? `'${keyword}' 검색 결과` : categoryId ? categories.find((category) => String(category.id) === categoryId)?.name : '전체 상품'}</h2>
        </div>
        {!isLoading && !error && <span>총 {total.toLocaleString('ko-KR')}개</span>}
        </div>

        {error && <p className="catalog-notice catalog-notice--error" role="alert">{error}</p>}
        {isLoading && !products.length ? (
          <p className="catalog-notice" role="status">상품을 불러오고 있습니다.</p>
        ) : (
          <section className={`catalog-grid${isLoading ? ' is-loading' : ''}`} aria-label="상품 목록" aria-busy={isLoading} ref={gridRef}>
          {products.map((product) => (
            <ProductCard key={product.id} product={product} onOpen={(item) => onNavigate(getCustomerProductDetailPath(item.id))} />
          ))}
          {!products.length && !error && <p className="catalog-empty">조건에 맞는 상품이 없습니다.</p>}
          </section>
        )}

        {totalPages > 1 && (
          <nav className="catalog-pagination" aria-label="상품 페이지">
          <button type="button" disabled={page <= 1} onClick={() => changePage(page - 1)}>이전</button>
          <span>{page} / {totalPages}</span>
          <button type="button" disabled={page >= totalPages} onClick={() => changePage(page + 1)}>다음</button>
          </nav>
        )}
      </main>

      <CatalogFooter />
    </div>
  )
}

export default ProductsPage
