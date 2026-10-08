// 고객이 공개 상품 상세내용과 관련 상품을 조회하는 페이지

import { useCallback, useEffect, useRef, useState } from 'react'
import WishlistLoginModal from '../components/common/wishlist-login-modal.jsx'
import { saveCheckoutDraft } from '../features/checkout/checkout.js'
import { addToCart, MAX_QUANTITY, toggleWishlist, useShopping } from '../features/cart/shopping-store.js'
import { getStoredUser } from '../api/user-auth.js'
import ProductCard from '../components/products/product-card.jsx'
import ProductInquiries from '../features/product-feedback/product-inquiries.jsx'
import ProductReviews from '../features/product-feedback/product-reviews.jsx'
import { DELIVERY_NOTICE, DELIVERY_SUMMARY, REFUND_NOTICE, TEST_SITE_NOTICE } from '../config/shop-policy.js'
import { getCatalogProduct } from '../api/products.js'
import CatalogFooter from '../components/products/catalog-footer.jsx'
import CatalogHeader from '../components/products/catalog-header.jsx'
import { CHECKOUT_PATH, CUSTOMER_PRODUCT_DETAIL_PREFIX, getCustomerProductDetailPath, getLoginPath, getPageTitle } from '../config/routes.js'
import { HeartIcon } from '../components/common/icons.jsx'

const DETAIL_TABS = [
  { id: 'product-description', label: '상품설명' },
  { id: 'product-information', label: '상세정보' },
  { id: 'product-reviews', label: '후기' },
  { id: 'product-inquiries', label: '문의' },
]


// 별점 설명 i 버튼: 마우스를 올리거나 키보드로 이동하면 바로, 터치 기기는 탭으로 말풍선을 열고 닫음(바깥 누르기·Esc로 닫기)
function RatingInfo({ text }) {
  const [isOpen, setIsOpen] = useState(false)
  const wrapRef = useRef(null)
  const isHoveringRef = useRef(false) // 마우스로 이미 열린 상태에서 클릭해도 닫히지 않게 구분

  useEffect(() => {
    if (!isOpen) return undefined
    const closeOnOutside = (event) => {
      if (!wrapRef.current?.contains(event.target)) setIsOpen(false)
    }
    const closeOnEscape = (event) => {
      if (event.key === 'Escape') setIsOpen(false)
    }
    document.addEventListener('pointerdown', closeOnOutside)
    document.addEventListener('keydown', closeOnEscape)
    return () => {
      document.removeEventListener('pointerdown', closeOnOutside)
      document.removeEventListener('keydown', closeOnEscape)
    }
  }, [isOpen])

  return (
    <span
      ref={wrapRef}
      className="catalog-rating__info-wrap"
      onPointerEnter={(event) => {
        if (event.pointerType !== 'mouse') return
        isHoveringRef.current = true
        setIsOpen(true)
      }}
      onPointerLeave={(event) => {
        if (event.pointerType !== 'mouse') return
        isHoveringRef.current = false
        setIsOpen(false)
      }}
    >
      <button
        className="catalog-rating__info"
        type="button"
        aria-label="최근 6개월 평균 별점 안내"
        aria-expanded={isOpen}
        aria-describedby={isOpen ? 'rating-info-tooltip' : undefined}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
        onClick={() => {
          if (!isHoveringRef.current) setIsOpen((current) => !current)
        }}
      >
        i
      </button>
      {isOpen && <span id="rating-info-tooltip" className="catalog-rating__tooltip" role="tooltip">{text}</span>}
    </span>
  )
}

// 경로의 변경 불가능한 상품 ID 기반 공개 상품 상세 조회
function ProductDetailPage({ onNavigate }) {
  const productId = Number(window.location.pathname.slice(CUSTOMER_PRODUCT_DETAIL_PREFIX.length))
  const invalidProductId = !Number.isInteger(productId) || productId <= 0
  const [product, setProduct] = useState(null)
  const [error, setError] = useState(invalidProductId ? '올바르지 않은 상품 주소입니다.' : '')
  const [quantity, setQuantity] = useState(1)
  const [reviewSummary, setReviewSummary] = useState(null) // 후기 구역이 불러온 평균·개수(상단 별점과 탭에 사용)
  const [activeTab, setActiveTab] = useState(DETAIL_TABS[0].id)
  const [isLoginModalOpen, setIsLoginModalOpen] = useState(false) // 비로그인 찜하기 안내 모달
  const { wishlistItems } = useShopping()
  const isWished = wishlistItems.some((item) => item.id === productId)

  // 구매하기: 로그인 고객만 진행(비로그인은 로그인 후 이 화면으로 복귀), 이 상품만 주문서(배송지 입력)로 넘김
  function handleBuyNow() {
    if (!getStoredUser()) {
      onNavigate(getLoginPath(`${window.location.pathname}${window.location.search}`))
      return
    }
    // 상세 본문(detail_html) 등 큰 값은 빼고 주문서에 필요한 필드만 보관
    saveCheckoutDraft({ items: [{ id: product.id, name: product.name, price: product.price, image_url: product.image_url, quantity }], fromCart: false })
    onNavigate(CHECKOUT_PATH)
  }

  // 찜하기: 비로그인이면 안내 모달을 띄우고 확인 시 로그인 페이지로 이동
  function handleWishlist() {
    if (!getStoredUser()) {
      setIsLoginModalOpen(true)
      return
    }
    toggleWishlist(product)
  }

  const handleSummaryChange = useCallback((summary) => setReviewSummary(summary), [])

  // 탭 클릭 시 해당 구역으로 스크롤
  function scrollToSection(sectionId) {
    document.getElementById(sectionId)?.scrollIntoView({ behavior: 'smooth' })
  }

  // 스크롤 위치에 맞춰 현재 구역 탭을 강조
  useEffect(() => {
    if (!product) return
    const handleScroll = () => {
      const current = [...DETAIL_TABS].reverse().find((tab) => (document.getElementById(tab.id)?.getBoundingClientRect().top ?? Infinity) <= 180)
      setActiveTab((current ?? DETAIL_TABS[0]).id)
    }
    window.addEventListener('scroll', handleScroll, { passive: true })
    handleScroll()
    return () => window.removeEventListener('scroll', handleScroll)
  }, [product])

  useEffect(() => {
    if (invalidProductId) return
    let isMounted = true
    getCatalogProduct(productId)
      .then((result) => {
        if (isMounted) setProduct(result.product)
      })
      .catch((requestError) => {
        if (isMounted) setError(requestError.message)
      })
    return () => {
      isMounted = false
    }
  }, [invalidProductId, productId])

  // 브라우저 탭 제목을 상품명으로 표시
  useEffect(() => {
    if (product) document.title = getPageTitle(null, product.name)
  }, [product])

  if (error) {
    return (
      <div className="catalog-page catalog-detail-page">
        <a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a>
        <CatalogHeader onNavigate={onNavigate} />
        <main id="catalog-main" className="catalog-detail-shell" tabIndex="-1">
          <div className="catalog-detail-state">
            <p className="catalog-notice catalog-notice--error" role="alert">{error}</p>
            <button className="catalog-detail-state__button" type="button" onClick={() => onNavigate('/')}>상품 목록으로 돌아가기</button>
          </div>
        </main>
        <CatalogFooter />
      </div>
    )
  }

  if (!product) return <div className="catalog-page"><a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a><CatalogHeader onNavigate={onNavigate} /><main id="catalog-main" tabIndex="-1"><p className="catalog-notice" role="status">상품을 불러오고 있습니다.</p></main><CatalogFooter /></div>

  return (
    <div className="catalog-page catalog-detail-page">
      <a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a>
      <CatalogHeader onNavigate={onNavigate} />
      <main id="catalog-main" className="catalog-detail-shell" tabIndex="-1">
        <article className="catalog-detail" aria-labelledby="product-title">
          <div className="catalog-detail__image">
            {product.image_url ? <img src={product.image_url} alt={product.image_description || product.name} /> : <span>NO IMAGE</span>}
          </div>
          <div className="catalog-detail__summary">
            <h1 id="product-title">{product.name}</h1>
            {reviewSummary && (
              <div className="catalog-rating">
                <svg className={`catalog-rating__star${reviewSummary.count ? '' : ' is-empty'}`} viewBox="0 0 24 24" aria-hidden="true">
                  <path d="m12 2.8 2.9 5.9 6.5.9-4.7 4.6 1.1 6.5L12 17.6l-5.8 3.1 1.1-6.5-4.7-4.6 6.5-.9L12 2.8Z" />
                </svg>
                {reviewSummary.count > 0 ? (
                  <>
                    <strong>{reviewSummary.average.toFixed(1)}</strong>
                    {reviewSummary.recent_average !== null && (
                      <span className="catalog-rating__recent">
                        (최근 6개월 {reviewSummary.recent_average.toFixed(2)}
                        <RatingInfo text="최근 6개월 동안 등록된 후기의 평균 별점입니다." />)
                      </span>
                    )}
                    <span className="catalog-rating__divider" aria-hidden="true" />
                    <button className="catalog-rating__reviews" type="button" onClick={() => scrollToSection('product-reviews')}>
                      {reviewSummary.count.toLocaleString('ko-KR')}건 리뷰
                    </button>
                  </>
                ) : (
                  <button className="catalog-rating__reviews" type="button" onClick={() => scrollToSection('product-reviews')}>아직 후기가 없어요</button>
                )}
              </div>
            )}
            <p className="detail-price"><strong>{product.price.toLocaleString('ko-KR')}</strong><span>원</span></p>
            <p className="detail-shipping-fee">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 6h11v9H3zM14 9h4l3 3v3h-7M7 18.5a1.5 1.5 0 1 0 0-.01M17 18.5a1.5 1.5 0 1 0 0-.01" /></svg>
              배송비 무료
            </p>

            <dl className="detail-info">
              <div>
                <dt>배송</dt>
                <dd>
                  <strong>{DELIVERY_SUMMARY.headline}</strong>
                  <span>{DELIVERY_SUMMARY.detail}</span>
                  <button type="button" onClick={() => scrollToSection('product-information')}>자세히 보기 ›</button>
                </dd>
              </div>
              <div>
                <dt>판매자</dt>
                <dd>아람 마켓</dd>
              </div>
              <div>
                <dt id="quantity-label">수량</dt>
                <dd>
                  <div className="catalog-quantity" role="group" aria-labelledby="quantity-label">
                    <button type="button" aria-label="수량 줄이기" disabled={quantity <= 1} onClick={() => setQuantity((current) => Math.max(1, current - 1))}>−</button>
                    <output aria-live="polite">{quantity}</output>
                    <button type="button" aria-label="수량 늘리기" disabled={quantity >= MAX_QUANTITY} onClick={() => setQuantity((current) => Math.min(MAX_QUANTITY, current + 1))}>+</button>
                  </div>
                </dd>
              </div>
            </dl>

            <div className="detail-total">
              <span>총 상품금액</span>
              <strong>{(product.price * quantity).toLocaleString('ko-KR')}<small>원</small></strong>
            </div>

            <div className="catalog-detail__actions">
              <button
                className={`catalog-detail__wish${isWished ? ' is-active' : ''}`}
                type="button"
                aria-pressed={isWished}
                aria-label={isWished ? '찜 해제' : '찜하기'}
                onClick={handleWishlist}
              >
                <HeartIcon />
              </button>
              <button className="catalog-detail__cart" type="button" onClick={() => addToCart(product, quantity)}>장바구니</button>
              <button className="catalog-detail__buy" type="button" onClick={handleBuyNow}>구매하기</button>
            </div>
          </div>
        </article>

        <nav className="detail-tabs" aria-label="상품 정보 구역">
          {DETAIL_TABS.map((tab) => (
            <button
              key={tab.id}
              className={activeTab === tab.id ? 'is-active' : ''}
              type="button"
              aria-current={activeTab === tab.id ? 'true' : undefined}
              onClick={() => scrollToSection(tab.id)}
            >
              {tab.label}
              {tab.id === 'product-reviews' && reviewSummary && <span> ({reviewSummary.count.toLocaleString('ko-KR')})</span>}
            </button>
          ))}
        </nav>

        <section id="product-description" className="detail-section" aria-label="상품설명">
          <div className="catalog-detail__content" dangerouslySetInnerHTML={{ __html: product.detail_html }} />
        </section>

        <section id="product-information" className="detail-section" aria-labelledby="product-information-title">
          <h2 id="product-information-title">상품고시정보</h2>
          <table className="detail-table">
            <tbody>
              <tr><th scope="row">상품명</th><td>{product.name}</td></tr>
              <tr><th scope="row">카테고리</th><td>{product.category}</td></tr>
              <tr><th scope="row">판매가</th><td>{product.price.toLocaleString('ko-KR')}원</td></tr>
              <tr><th scope="row">판매자</th><td>아람 마켓</td></tr>
              <tr><th scope="row">배송 안내</th><td><ul className="detail-policy">{DELIVERY_NOTICE.map((line) => <li key={line}>{line}</li>)}</ul></td></tr>
              <tr><th scope="row">취소·환불 안내</th><td><ul className="detail-policy">{REFUND_NOTICE.map((line) => <li key={line}>{line}</li>)}</ul></td></tr>
              <tr><th scope="row">유의사항</th><td>{TEST_SITE_NOTICE}</td></tr>
            </tbody>
          </table>
        </section>

        <section id="product-reviews" className="detail-section" aria-labelledby="product-reviews-title">
          <div className="detail-section__heading">
            <h2 id="product-reviews-title">상품 후기 {reviewSummary && <span>({reviewSummary.count.toLocaleString('ko-KR')})</span>}</h2>
          </div>
          <ProductReviews productId={productId} onNavigate={onNavigate} onSummaryChange={handleSummaryChange} />
        </section>

        <section id="product-inquiries" className="detail-section" aria-labelledby="product-inquiries-title">
          <div className="detail-section__heading">
            <h2 id="product-inquiries-title">상품 문의</h2>
          </div>
          <ul className="detail-notes">
            <li>상품에 대해 궁금한 점을 남겨 주세요. 비밀글은 작성자만 볼 수 있어요.</li>
            <li>배송·결제·교환·환불 관련 문의도 이곳에 남기시면 순서대로 답변드립니다.</li>
          </ul>
          <ProductInquiries productId={productId} onNavigate={onNavigate} />
        </section>

        {product.related_products.length > 0 && (
          <section className="catalog-related">
            <div className="catalog-related__heading">
              <div>
                <p>YOU MAY ALSO LIKE</p>
                <h2>함께 보면 좋은 상품</h2>
              </div>
              <span>같은 카테고리에서 엄선했어요.</span>
            </div>
            <div className="catalog-grid">
              {product.related_products.map((related) => (
                <ProductCard key={related.id} product={related} onOpen={(item) => onNavigate(getCustomerProductDetailPath(item.id))} />
              ))}
            </div>
          </section>
        )}
      </main>
      <WishlistLoginModal
        isOpen={isLoginModalOpen}
        onClose={() => setIsLoginModalOpen(false)}
        onConfirm={() => {
          setIsLoginModalOpen(false)
          onNavigate(getLoginPath(`${window.location.pathname}${window.location.search}`))
        }}
      />
      <CatalogFooter />
    </div>
  )
}

export default ProductDetailPage
