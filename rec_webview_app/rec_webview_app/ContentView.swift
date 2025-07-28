import SwiftUI
import WebKit

struct WebView: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> WKWebView {
        let webView = WKWebView()
        webView.navigationDelegate = context.coordinator
        webView.scrollView.bounces = false
        webView.scrollView.isScrollEnabled = false
        webView.translatesAutoresizingMaskIntoConstraints = false
        return webView
    }

    func updateUIView(_ uiView: WKWebView, context: Context) {
        let request = URLRequest(url: url)
        uiView.load(request)
    }

    func makeCoordinator() -> Coordinator {
        Coordinator()
    }

    class Coordinator: NSObject, WKNavigationDelegate {
        func webView(_ webView: WKWebView, didFail navigation: WKNavigation!, withError error: Error) {
            print("Navigation error: \(error.localizedDescription)")
        }

        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
            print("Provisional navigation error: \(error.localizedDescription)")
        }

        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
            print("✅ Finished loading URL: \(webView.url?.absoluteString ?? "unknown")")
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
            urlString = "http://192.168.86.42:3000/"
        case .phone:
            urlString = "http://192.168.86.42:3000/mobile/index.html#"
        default:
            urlString = "http://192.168.86.42:3000/"
        }
        return URL(string: urlString)!
    }
}
