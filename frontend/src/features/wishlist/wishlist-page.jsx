// 찜한 상품을 카테고리별로 모아 보고 장바구니 담기·찜 해제를 하는 고객 찜 페이지

import { useState } from 'react'
import CatalogFooter from '../../components/products/catalog-footer.jsx'
import CatalogHeader from '../../components/products/catalog-header.jsx'
import ProductCard from '../../components/products/product-card.jsx'
import { getCustomerProductDetailPath } from '../../config/routes.js'
import { toggleWishlist, useShopping } from '../cart/shopping-store.js'
import { HeartIcon } from '../../components/common/icons.jsx'

const ALL_CATEGORIES = '전체'

// 찜 목록(로그인 필요)과 카테고리 필터
function WishlistPage({ onNavigate }) {
  const { wishlistItems, isLoading } = useShopping()
  const [category, setCategory] = useState(ALL_CATEGORIES)
  const categories = [ALL_CATEGORIES, ...new Set(wishlistItems.map((item) => item.category))]
  const activeCategory = categories.includes(category) ? category : ALL_CATEGORIES // 선택한 카테고리의 마지막 상품을 해제하면 전체로 복귀
  const visibleItems = activeCategory === ALL_CATEGORIES ? wishlistItems : wishlistItems.filter((item) => item.category === activeCategory)

  return (
    <div className="catalog-page wishlist-page">
      <a className="catalog-skip-link" href="#catalog-main">본문 바로가기</a>
      <CatalogHeader onNavigate={onNavigate} />
      <main id="catalog-main" className="wishlist-shell" tabIndex="-1">
        <header className="cart-heading">
          <p>WISHLIST</p>
          <h1>찜 목록{wishlistItems.length > 0 && <> <span>{wishlistItems.length}</span></>}</h1>
        </header>

        {wishlistItems.length > 0 && (
          <nav className="wishlist-categories" aria-label="찜한 상품 카테고리">
            {categories.map((name) => (
              <button key={name} className={name === activeCategory ? 'is-active' : ''} type="button" aria-pressed={name === activeCategory} onClick={() => setCategory(name)}>
                {name}
              </button>
            ))}
          </nav>
        )}

        {isLoading && wishlistItems.length === 0 ? (
          <p className="catalog-notice" role="status">찜한 상품을 불러오고 있습니다.</p>
        ) : wishlistItems.length === 0 ? (
          <div className="wishlist-empty">
            <HeartIcon />
            <strong>찜한 상품이 없어요</strong>
            <span>마음에 드는 상품을 찜해보세요</span>
          </div>
        ) : (
          <section className="wishlist-grid" aria-label="찜한 상품 목록">
            {visibleItems.map((item) => (
              <ProductCard key={item.id} product={item} onOpen={(product) => onNavigate(getCustomerProductDetailPath(product.id))} onRemove={toggleWishlist} />
            ))}
          </section>
        )}
      </main>
      <CatalogFooter />
    </div>
  )
}

export default WishlistPage
