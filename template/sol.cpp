#include <bits/stdc++.h>
#include <core.hpp>

#if LOCAL_DEBUG
ifstream is("test/data/default/debug.in");
#else
auto& is = cin;
#endif // LOCAL_DEBUG

#if NOT_RELEASE_MODE
template <class... T>
void logerr(T... _) {
#if __cplusplus >= 201703L
  ((cerr << _), ...);
#else
  int t[] {(cerr << _, 0)...};
#endif // C++17
}
#endif // !NOT_RELEASE_MODE

void solve();

/** other custom headers **/

/** other custom headers **/

int main() {
  ios::sync_with_stdio(0);
  cin.tie(0);
#if ONE_INPUT_MULTIPLE_TESTS
  int _;
  is >> _;
  while (_--)
    solve();
#else
  solve();
#endif // ONE_INPUT_MULTIPLE_TESTS
}

void solve() {
  
}
