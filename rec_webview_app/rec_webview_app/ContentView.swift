import SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.allowsInlineMediaPlayback = true
        configuration.mediaTypesRequiringUserActionForPlayback = []
        
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let dataStore = WKWebsiteDataStore.default()
        let types = WKWebsiteDataStore.allWebsiteDataTypes()
        dataStore.fetchDataRecords(ofTypes: types) { records in
            dataStore.removeData(ofTypes: types, for: records) {
                print("✅ Cleared web cache")
            }
        }
        webView.navigationDelegate = context.coordinator
        webView.scrollView.bounces = false
        webView.scrollView.isScrollEnabled = false
        webView.translatesAutoresizingMaskIntoConstraints = false
        
        // Force allow HTTP connections
        webView.configuration.preferences.javaScriptEnabled = true
        webView.configuration.preferences.javaScriptCanOpenWindowsAutomatically = true
        
        print("🔧 WebView configured for URL: \(url.absoluteString)")
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        uiView.load(request)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("❌ Navigation error: \(error.localizedDescription)")
            print("❌ Error code: \((error as NSError).code)")
            print("❌ Error domain: \((error as NSError).domain)")
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            print("❌ Provisional navigation error: \(error.localizedDescription)")
            print("❌ Error code: \((error as NSError).code)")
            print("❌ Error domain: \((error as NSError).domain)")
            
            // Try to handle ATS errors specifically
            let nsError = error as NSError
            if nsError.domain == NSURLErrorDomain && nsError.code == NSURLErrorAppTransportSecurityRequiresSecureConnection {
                print("🔧 ATS Error detected - trying alternative approach")
            }
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("✅ Finished loading URL: \(webView.url?.absoluteString ?? "unknown")")
        }
        
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            print("🔧 Navigation decision for: \(navigationAction.request.url?.absoluteString ?? "unknown")")
            decisionHandler(.allow)
        }
    }
}

struct ContentView: View {
    var body: some View {
        WebView(url: resolvedURL)
            .ignoresSafeArea()
    }

    private var resolvedURL: URL {
        let urlString: String
        switch UIDevice.current.userInterfaceIdiom {
        case .pad:
            urlString = "https://macbook-pro.tail30eef4.ts.net/"
        case .phone:
            urlString = "https://macbook-pro.tail30eef4.ts.net/mobile/index.html"
        default:
            urlString = "https://macbook-pro.tail30eef4.ts.net/"
        }
        print("🔧 Attempting to load URL: \(urlString)")
        return URL(string: urlString)!
    }
}
