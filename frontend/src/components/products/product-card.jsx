// 상품 목록·관련 상품 공통 카드: 이미지 아래 전폭 '담기' 버튼(컬리 방식)으로 장바구니에 담음

import { addToCart } from '../../features/cart/shopping-store.js'

// 이미지·상품 정보는 상세 이동, 가운데 '담기' 버튼은 장바구니 담기
function ProductCard({ product, onOpen }) {
  return (
    <article className="product-card">
      <button className="product-card__media" type="button" tabIndex={-1} aria-hidden="true" onClick={() => onOpen(product)}>
        {product.image_url ? <img src={product.image_url} alt="" /> : <span className="product-card__placeholder">NO IMAGE</span>}
      </button>
      <button className="product-card__add" type="button" aria-label={`${product.name} 장바구니에 담기`} onClick={() => addToCart(product)}>
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3 5h2.4l1.5 9.2a2 2 0 0 0 2 1.7h8.2a2 2 0 0 0 2-1.6L20.4 8H6" />
          <circle cx="9.5" cy="19.2" r="1.3" />
          <circle cx="17" cy="19.2" r="1.3" />
        </svg>
        담기
      </button>
      <button className="product-card__info" type="button" onClick={() => onOpen(product)}>
        <span className="product-card__category">{product.category}</span>
        <strong>{product.name}</strong>
        <span className="product-card__price">{product.price.toLocaleString('ko-KR')}원</span>
      </button>
    </article>
  )
}

export default ProductCard
