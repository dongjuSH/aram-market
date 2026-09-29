// 고객 상품 화면 공통 헤더: 상단 회원가입·로그인(로그인 시 닉네임·로그아웃), 브랜드·검색, 우측 찜·장바구니·마이페이지 아이콘

import { useEffect, useState } from 'react'
import { getStoredUser, signOut } from '../../api/user-auth.js'
import { useShopping } from '../../features/cart/shopping-store.js'
import { CART_PATH, getLoginPath, USER_MY_PAGE_PATH, USER_SIGNUP_PATH } from '../../config/routes.js'

const WISHLIST_PATH = `${USER_MY_PAGE_PATH}?section=wishlist` // 마이 페이지의 찜한 상품 구역

// 고객 상품 목록으로 이동 가능한 브랜드 헤더
function CatalogHeader({ onNavigate, searchValue, onSearchValueChange, onSearch, hideLogin = false }) {
  const [isScrolled, setIsScrolled] = useState(() => window.scrollY > 0)
  const storedUser = getStoredUser()
  const isLoggedIn = Boolean(storedUser)
  const { items, toast } = useShopping()
  const cartCount = items.length
  // 이미 지난 담기 기록은 화면 이동 시 다시 띄우지 않도록 처음 값을 숨김 처리
  const [hiddenAt, setHiddenAt] = useState(() => toast?.at ?? 0)
  const isToastVisible = Boolean(toast) && toast.at !== hiddenAt
  const currentPath = `${window.location.pathname}${window.location.search}`

  // 상품을 담거나 오류가 나면 잠깐 안내를 띄움
  useEffect(() => {
    if (!toast) return
    const timer = setTimeout(() => setHiddenAt(toast.at), 2600)
    return () => clearTimeout(timer)
  }, [toast])

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 0)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  // 마이 페이지를 거치지 않고 바로 로그아웃
  const logout = async () => {
    await signOut()
    onNavigate('/', { replace: true })
  }

  return (
    <>
      {(isLoggedIn || !hideLogin) && (
        <div className="catalog-utility">
          <div className="catalog-utility__inner">
            {isLoggedIn ? (
              <>
                <span>{storedUser.nickname}님</span>
                <button type="button" onClick={logout}>로그아웃</button>
              </>
            ) : (
              <>
                <button className="is-accent" type="button" onClick={() => onNavigate(USER_SIGNUP_PATH)}>회원가입</button>
                <button type="button" onClick={() => onNavigate(getLoginPath(currentPath))}>로그인</button>
              </>
            )}
          </div>
        </div>
      )}
      <header className={`catalog-header${isScrolled ? ' is-scrolled' : ''}`}>
        <div className={`catalog-header__inner${onSearch ? '' : ' catalog-header__inner--without-search'}`}>
          <a
            className="catalog-brand"
            aria-label="아람 마켓 메인 페이지로 이동"
            href="/"
            onClick={(event) => {
              event.preventDefault()
              onNavigate('/')
            }}
          >
            <img src="/assets/aram-market-fruit.svg" alt="" />
            <strong>아람 마켓</strong>
          </a>

          {onSearch && (
            <form className="catalog-header-search" role="search" onSubmit={onSearch}>
              <input
                type="search"
                aria-label="상품 검색"
                placeholder="상품명을 검색해 주세요"
                value={searchValue}
                onChange={onSearchValueChange}
              />
              <button type="submit" aria-label="상품명 검색">
                <svg viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="10.5" cy="10.5" r="6.5" />
                  <path d="m15.5 15.5 4 4" />
                </svg>
              </button>
            </form>
          )}

          <div className="catalog-header__actions" role="group" aria-label="고객 메뉴">
            <button type="button" aria-label="찜 목록" title="찜 목록" onClick={() => onNavigate(isLoggedIn ? WISHLIST_PATH : getLoginPath(WISHLIST_PATH))}>
              <svg className="catalog-header__menu-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2Z" />
              </svg>
            </button>
            <button className="catalog-header__cart" type="button" aria-label={`장바구니, 담긴 상품 ${cartCount}개`} title="장바구니" onClick={() => onNavigate(CART_PATH)}>
              <svg className="catalog-header__menu-icon catalog-header__cart-icon" viewBox="0 0 24 24" aria-hidden="true">
                <path d="M3 5h2.4l1.5 9.2a2 2 0 0 0 2 1.7h8.2a2 2 0 0 0 2-1.6L20.4 8H6" />
                <circle cx="9.5" cy="19.2" r="1.3" />
                <circle cx="17" cy="19.2" r="1.3" />
              </svg>
              {cartCount > 0 && (
                <span className="catalog-header__cart-count" aria-hidden="true">
                  <span>{cartCount > 99 ? '99+' : cartCount}</span>
                </span>
              )}
            </button>
            {isLoggedIn && (
              <button type="button" aria-label="마이 페이지" title="마이 페이지" onClick={() => onNavigate(USER_MY_PAGE_PATH)}>
                <svg className="catalog-header__menu-icon" viewBox="0 0 24 24" aria-hidden="true">
                  <circle cx="12" cy="7.5" r="3.5" />
                  <path d="M5 20a7 7 0 0 1 14 0" />
                </svg>
              </button>
            )}
          </div>
        </div>
        {isToastVisible && (
          <div className={`catalog-cart-toast${toast.type === 'error' ? ' catalog-cart-toast--error' : ''}`} role={toast.type === 'error' ? 'alert' : 'status'}>
            <span>{toast.message}</span>
            {toast.actionPath && (
              <button type="button" onClick={() => { setHiddenAt(toast.at); onNavigate(toast.actionPath) }}>{toast.actionLabel}</button>
            )}
          </div>
        )}
      </header>
    </>
  )
}

export default CatalogHeader
