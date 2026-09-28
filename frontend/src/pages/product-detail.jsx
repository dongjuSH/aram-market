// 고객이 공개 상품 상세내용과 관련 상품을 조회하는 페이지

import { useEffect, useState } from 'react'
import { getCatalogProduct } from '../api/products.js'
import CatalogFooter from '../components/products/catalog-footer.jsx'
import CatalogHeader from '../components/products/catalog-header.jsx'
import { CUSTOMER_PRODUCT_DETAIL_PREFIX, getCustomerProductDetailPath } from '../config/routes.js'


// 경로의 변경 불가능한 상품 ID 기반 공개 상품 상세 조회
function ProductDetailPage({ onNavigate }) {
  const productId = Number(window.location.pathname.slice(CUSTOMER_PRODUCT_DETAIL_PREFIX.length))
  const invalidProductId = !Number.isInteger(productId) || productId <= 0
  const [product, setProduct] = useState(null)
  const [error, setError] = useState(invalidProductId ? '올바르지 않은 상품 주소입니다.' : '')

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
        <nav className="catalog-breadcrumb" aria-label="현재 위치">
          <ol>
            <li><button type="button" onClick={() => onNavigate('/')}>홈</button></li>
            <li><span aria-hidden="true">/</span>{product.category}</li>
            <li><span aria-hidden="true">/</span><strong aria-current="page">{product.name}</strong></li>
          </ol>
        </nav>

        <article className="catalog-detail" aria-labelledby="product-title">
          <div className="catalog-detail__image">
            {product.image_url ? <img src={product.image_url} alt={product.image_description || product.name} /> : <span>NO IMAGE</span>}
          </div>
          <div className="catalog-detail__summary">
            <p className="catalog-detail__category">{product.category}</p>
            <h1 id="product-title">{product.name}</h1>
            <p className="catalog-detail__lead">아람 마켓이 일상에 필요한 가치를 기준으로 엄선한 상품입니다.</p>
            <div className="catalog-detail__price">
              <span>판매가</span>
              <strong>{product.price.toLocaleString('ko-KR')}<small>원</small></strong>
            </div>
            <dl className="catalog-detail__facts">
              <div>
                <dt>카테고리</dt>
                <dd>{product.category}</dd>
              </div>
              <div>
                <dt>상품 안내</dt>
                <dd>상세정보를 확인해 주세요</dd>
              </div>
            </dl>
            <button
              className="catalog-detail__more"
              type="button"
              onClick={() => document.getElementById('product-information')?.scrollIntoView({ behavior: 'smooth' })}
            >
              상품 상세정보 보기
              <span aria-hidden="true">↓</span>
            </button>
          </div>
        </article>

        <section id="product-information" className="catalog-detail-information" aria-labelledby="product-information-title">
          <header>
            <p>PRODUCT STORY</p>
            <h2 id="product-information-title">상품 상세정보</h2>
            <span>상품의 특징과 구성 정보를 확인해 주세요.</span>
          </header>
          <div className="catalog-detail__content" dangerouslySetInnerHTML={{ __html: product.detail_html }} />
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
                <button key={related.id} className="catalog-card" type="button" onClick={() => onNavigate(getCustomerProductDetailPath(related.id))}>
                  {related.image_url ? (
                    <img src={related.image_url} alt={related.image_description || related.name} />
                  ) : (
                    <span className="catalog-card__placeholder" aria-hidden="true">NO IMAGE</span>
                  )}
                  <span className="catalog-card__category">{related.category}</span>
                  <strong>{related.name}</strong>
                  <span className="catalog-card__price">{related.price.toLocaleString('ko-KR')}원</span>
                </button>
              ))}
            </div>
          </section>
        )}
      </main>
      <CatalogFooter />
    </div>
  )
}

export default ProductDetailPage
