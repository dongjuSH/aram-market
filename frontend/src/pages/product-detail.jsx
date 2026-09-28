// 고객이 공개 상품 상세내용과 관련 상품을 조회하는 페이지

import { useEffect, useState } from 'react'
import { getCatalogProduct } from '../api/products.js'


// URL 상품 ID 기반 공개 상품 상세 조회
function ProductDetailPage({ onNavigate }) {
  const productId = Number(new URLSearchParams(window.location.search).get('id'))
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
      <main className="catalog-page catalog-detail-page">
        <button className="catalog-back" type="button" onClick={() => onNavigate('/products')}>← 상품 목록</button>
        <p className="catalog-notice catalog-notice--error" role="alert">{error}</p>
      </main>
    )
  }

  if (!product) return <main className="catalog-page"><p className="catalog-notice">상품을 불러오고 있습니다.</p></main>

  return (
    <main className="catalog-page catalog-detail-page">
      <button className="catalog-back" type="button" onClick={() => onNavigate('/products')}>← 상품 목록</button>
      <article className="catalog-detail">
        <div className="catalog-detail__image">
          {product.image_url ? <img src={product.image_url} alt={product.image_description || product.name} /> : <span>NO IMAGE</span>}
        </div>
        <div className="catalog-detail__summary">
          <p>{product.category}</p>
          <h1>{product.name}</h1>
          <span>{product.code}</span>
          <strong>{product.price.toLocaleString('ko-KR')}원</strong>
        </div>
        <section className="catalog-detail__content" aria-label="상품 상세내용" dangerouslySetInnerHTML={{ __html: product.detail_html }} />
      </article>

      {product.related_products.length > 0 && (
        <section className="catalog-related">
          <h2>관련 상품</h2>
          <div className="catalog-grid">
            {product.related_products.map((related) => (
              <button key={related.id} className="catalog-card" type="button" onClick={() => onNavigate(`/products/detail?id=${related.id}`)}>
                {related.image_url && <img src={related.image_url} alt={related.image_description || related.name} />}
                <strong>{related.name}</strong>
                <span className="catalog-card__price">{related.price.toLocaleString('ko-KR')}원</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </main>
  )
}

export default ProductDetailPage
