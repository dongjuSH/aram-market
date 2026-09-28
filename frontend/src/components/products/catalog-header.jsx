// 고객 상품 화면의 브랜드·검색과 장바구니·로그인 액션을 제공하는 공통 헤더

import { useEffect, useState } from 'react'


// 고객 상품 목록으로 이동 가능한 브랜드 헤더
function CatalogHeader({ onNavigate, searchValue, onSearchValueChange, onSearch }) {
  const [isScrolled, setIsScrolled] = useState(() => window.scrollY > 0)
  const isLoggedIn = Boolean(sessionStorage.getItem('userAccessToken'))

  useEffect(() => {
    const handleScroll = () => setIsScrolled(window.scrollY > 0)
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [])

  return (
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
          <button className="catalog-header__cart" type="button" aria-label="장바구니" title="장바구니">
            <svg className="catalog-header__menu-icon catalog-header__cart-icon" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M3 5h2.4l1.5 9.2a2 2 0 0 0 2 1.7h8.2a2 2 0 0 0 2-1.6L20.4 8H6" />
              <circle cx="9.5" cy="19.2" r="1.3" />
              <circle cx="17" cy="19.2" r="1.3" />
            </svg>
            <span className="catalog-header__action-label">장바구니</span>
            <span className="catalog-header__cart-count" aria-label="담긴 상품 0개">
              <span aria-hidden="true">0</span>
            </span>
          </button>
          <button
            className="catalog-header__login"
            type="button"
            aria-label={isLoggedIn ? '마이 페이지' : '로그인'}
            onClick={() => onNavigate(isLoggedIn ? '/user' : '/user/login')}
          >
            <svg className="catalog-header__menu-icon catalog-header__user-icon" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="7.5" r="3.5" />
              <path d="M5 20a7 7 0 0 1 14 0" />
            </svg>
            <span className="catalog-header__action-label">{isLoggedIn ? '마이 페이지' : '로그인'}</span>
          </button>
        </div>
      </div>
    </header>
  )
}

export default CatalogHeader
