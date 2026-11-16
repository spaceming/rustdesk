use base::message_proto::{message, option_message::BoolOption, *};
use hbb_common::{config::Config, protobuf::Message as _, tcp, tokio, ResultType, Stream};
use sha2::{Digest, Sha256};

const PASSWORD: &str = "local-only-16703-validation";

#[tokio::main]
async fn main() -> ResultType<()> {
    if !matches!(std::env::args().nth(1).as_deref(), Some("server" | "client")) {
        return Ok(());
    }
    if std::env::args().nth(1).as_deref() == Some("server") {
        Config::set_permanent_password(PASSWORD);
        Config::set_option("approve-mode".into(), "password".into());
        Config::set_option("verification-method".into(), "use-permanent-password".into());
        let server = librustdesk::new();
        let listener = tokio::net::TcpListener::bind("127.0.0.1:21183").await?;
        println!("{{\"event\":\"listening\"}}");
        loop {
            let (socket, addr) = listener.accept().await?;
            let local = socket.local_addr()?;
            let server = server.clone();
            tokio::spawn(async move {
                if let Err(err) = librustdesk::create_tcp_connection(
                    server, Stream::from(socket, local), addr, false,
                    librustdesk::ConnectionMeta {control_permissions:None, controlled_context:None},
                ).await {
                    eprintln!("connection: {err:?}");
                }
            });
        }
    }
    let mut stream = tcp::FramedStream::new("127.0.0.1:21183", None, 3000).await?;
    while let Some(data) = stream.next().await {
        let msg = Message::parse_from_bytes(&data?)?;
        match msg.union {
            Some(message::Union::Hash(hash)) => {
                let h1 = Sha256::digest([PASSWORD.as_bytes(), hash.salt.as_bytes()].concat());
                let password = Sha256::digest([h1.as_slice(), hash.challenge.as_bytes()].concat());
                let mut request = Message::new();
                request.set_login_request(LoginRequest {
                    username:"127.0.0.1".into(), my_id:"16703-validation-controller".into(),
                    my_name:"X11 cursor regression validation".into(), version:"1.5.3".into(),
                    my_platform:"Linux".into(), password:password.to_vec().into(),
                    option:Some(OptionMessage {
                        show_remote_cursor:BoolOption::Yes.into(),
                        disable_audio:BoolOption::Yes.into(),
                        disable_clipboard:BoolOption::Yes.into(),
                        ..Default::default()
                    }).into(), ..Default::default()
                });
                stream.send(&request).await?;
            }
            Some(message::Union::LoginResponse(response)) => {
                println!("{}",serde_json::json!({"event":"login","response":format!("{response:?}")}));
            }
            Some(message::Union::CursorData(cursor)) => {
                let pixels = hbb_common::compress::decompress(&cursor.colors);
                println!("{}",serde_json::json!({"event":"cursor","id":cursor.id,
                    "width":cursor.width,"height":cursor.height,
                    "visible_pixels":pixels.chunks_exact(4).filter(|p|p[3]!=0).count()}));
            }
            Some(message::Union::CursorId(id)) => println!("{}",serde_json::json!({"event":"cursor-id","id":id})),
            Some(message::Union::TestDelay(delay)) => {
                let mut reply=Message::new();
                reply.set_test_delay(delay);
                stream.send(&reply).await?;
            }
            Some(message::Union::Misc(misc)) => println!("{}",serde_json::json!({"event":"misc","value":format!("{misc:?}")})),
            _ => (),
        }
    }
    Ok(())
}
