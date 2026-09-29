// 장바구니·찜 저장소: 로그인 고객은 서버 DB, 비로그인 장바구니는 메모리(새로고침 시 초기화), 찜은 로그인 필요

import { useSyncExternalStore } from 'react'
import { addCartItem, getCart, mergeCart, removeCartItems, setCartItemQuantity } from '../../api/cart.js'
import { getStoredUser, USER_AUTH_CHANGE_EVENT } from '../../api/user-auth.js'
import { addWishlistItem, getWishlist, removeWishlistItem } from '../../api/wishlist.js'
import { CART_PATH, getLoginPath } from '../../config/routes.js'
import { clearCheckoutDraft } from '../checkout/checkout.js'

export const MAX_QUANTITY = 99

let loggedInUserId = getStoredUser()?.id ?? null
let state = {
  items: [],
  wishlistItems: [], // 서버에서 받은 찜 상품(로그인 고객만)
  isLoading: Boolean(loggedInUserId), // 로그인 상태로 시작하면 서버 장바구니를 불러오는 동안 true
  toast: null, // { message, type, at, actionLabel, actionPath }: 헤더에서 잠깐 보여주는 담기·오류 안내
}
const listeners = new Set()

// 새 상태 객체로 교체해 구독 중인 화면을 다시 그리게 함
function setState(patch) {
  state = { ...state, ...patch }
  listeners.forEach((listener) => listener())
}

function subscribe(listener) {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

function showToast(message, type = 'info', action = null) {
  setState({ toast: { message, type, at: Date.now(), actionLabel: action?.label, actionPath: action?.path } })
}

// 화면에서 장바구니·찜 상태를 구독
export function useShopping() {
  return useSyncExternalStore(subscribe, () => state)
}

// 서버 장바구니·찜을 다시 불러와 화면 상태로 반영(로그인 상태일 때만)
async function loadServerCart() {
  if (!getStoredUser()) return
  try {
    const [cart, wishlist] = await Promise.all([getCart(), getWishlist()])
    setState({ items: cart.items, wishlistItems: wishlist.items, isLoading: false })
  } catch {
    setState({ isLoading: false })
  }
}

// 로그인 직후 비로그인으로 담아 둔 장바구니를 계정에 합치고 찜을 불러오며, 로그아웃하면 화면 상태를 비움
async function syncWithAuth() {
  const user = getStoredUser()
  if (!user) {
    loggedInUserId = null
    clearCheckoutDraft() // 공용 PC에서 다음 사람에게 배송지·주문 상품이 보이지 않도록 함께 지움
    setState({ items: [], wishlistItems: [], isLoading: false })
    return
  }
  if (loggedInUserId === user.id) return // 회원정보 갱신 등 같은 사용자의 표식 변경은 무시
  const guestItems = state.items
  loggedInUserId = user.id
  setState({ isLoading: true })
  try {
    const cart = guestItems.length ? await mergeCart(guestItems) : await getCart()
    setState({ items: cart.items, wishlistItems: (await getWishlist()).items, isLoading: false })
  } catch {
    setState({ isLoading: false })
  }
}
window.addEventListener(USER_AUTH_CHANGE_EVENT, syncWithAuth)

// 다른 탭에서 바뀐 서버 장바구니를 이 탭이 다시 보일 때 최신으로 맞춤
window.addEventListener('focus', loadServerCart)
if (loggedInUserId) loadServerCart()

// 상품 담기: 로그인이면 서버에 저장하고 응답의 최신 장바구니를 반영, 비로그인이면 메모리에 저장
export async function addToCart(product, quantity = 1) {
  if (getStoredUser()) {
    try {
      const result = await addCartItem(product.id, quantity)
      setState({ items: result.items })
      showToast(`${product.name} 상품을 장바구니에 담았습니다.`, 'info', { label: '장바구니 보기', path: CART_PATH })
    } catch (error) {
      showToast(error.message, 'error')
    }
    return
  }
  const existing = state.items.find((item) => item.id === product.id)
  const items = existing
    ? state.items.map((item) => (item.id === product.id ? { ...item, quantity: Math.min(MAX_QUANTITY, item.quantity + quantity) } : item))
    : [
        ...state.items,
        {
          id: product.id,
          name: product.name,
          category: product.category,
          price: product.price,
          image_url: product.image_url,
          image_description: product.image_description,
          quantity: Math.min(MAX_QUANTITY, quantity),
        },
      ]
  setState({ items })
  showToast(`${product.name} 상품을 장바구니에 담았습니다.`, 'info', { label: '장바구니 보기', path: CART_PATH })
}

export async function updateCartQuantity(productId, quantity) {
  const nextQuantity = Math.min(MAX_QUANTITY, Math.max(1, quantity))
  if (getStoredUser()) {
    try {
      setState({ items: (await setCartItemQuantity(productId, nextQuantity)).items })
    } catch (error) {
      showToast(error.message, 'error')
    }
    return
  }
  setState({ items: state.items.map((item) => (item.id === productId ? { ...item, quantity: nextQuantity } : item)) })
}

export async function removeFromCart(productIds) {
  if (getStoredUser()) {
    try {
      setState({ items: (await removeCartItems(productIds)).items })
    } catch (error) {
      showToast(error.message, 'error')
    }
    return
  }
  const removeIds = new Set(productIds)
  setState({ items: state.items.filter((item) => !removeIds.has(item.id)) })
}

// 찜하기·해제: 로그인 고객만 가능하고, 비로그인이면 로그인 안내와 로그인 이동 버튼을 띄움
export async function toggleWishlist(product) {
  if (!getStoredUser()) {
    showToast('찜하기는 로그인 후 이용할 수 있어요.', 'info', {
      label: '로그인',
      path: getLoginPath(`${window.location.pathname}${window.location.search}`),
    })
    return
  }
  const isWished = state.wishlistItems.some((item) => item.id === product.id)
  try {
    const result = isWished ? await removeWishlistItem(product.id) : await addWishlistItem(product.id)
    setState({ wishlistItems: result.items })
    if (!isWished) showToast('찜한 상품에 담았습니다. 마이 페이지에서 확인할 수 있어요.', 'info', { label: '찜 목록 보기', path: '/user' })
  } catch (error) {
    showToast(error.message, 'error')
  }
}
