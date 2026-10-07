// 상품 목록·관련 상품 공통 카드: 이미지 아래 전폭 '담기' 버튼(컬리 방식)으로 장바구니에 담음

import { addToCart } from '../../features/cart/shopping-store.js'
import { HeartIcon, StarIcon } from '../../components/common/icons.jsx'

// 이미지·상품 정보는 상세 이동, 가운데 '담기' 버튼은 장바구니 담기, onRemove가 있으면 이미지 위 하트로 찜 해제
function ProductCard({ product, onOpen, onRemove }) {
  return (
    <article className={`product-card${onRemove ? ' product-card--removable' : ''}`}>
      {/* 이미지는 마우스 클릭 전용 보조 이동이라 포커스를 받지 않는 div로 둔다(키보드·스크린리더는 아래 상품 정보 버튼 사용) */}
      <div className="product-card__media" aria-hidden="true" onClick={() => onOpen(product)}>
        {product.image_url ? <img src={product.image_url} alt="" /> : <span className="product-card__placeholder">NO IMAGE</span>}
      </div>
      {onRemove && (
        <button className="product-card__unwish" type="button" aria-label={`${product.name} 찜 해제`} title="찜 해제" onClick={() => onRemove(product)}>
          <HeartIcon />
        </button>
      )}
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
        {product.review_count > 0 ? (
          <span className="product-card__rating">
            <StarIcon />
            <b>{product.review_average.toFixed(1)}</b>
            <span aria-hidden="true">·</span>
            <span>후기 {product.review_count.toLocaleString('ko-KR')}</span>
          </span>
        ) : (
          <span className="product-card__rating product-card__rating--empty">후기 없음</span>
        )}
      </button>
    </article>
  )
}

export default ProductCard
