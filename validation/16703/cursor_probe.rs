use std::io::{self, BufRead, Write};

fn main() {
    for line in io::stdin().lock().lines() {
        let label = line.expect("read probe command");
        if label == "quit" {
            break;
        }
        let result = match librustdesk::get_cursor().expect("get actual XFixes cursor") {
            Some(id) => {
                let data = librustdesk::get_cursor_data(id).expect("get actual cursor image");
                let visible = data.colors.chunks_exact(4).filter(|p| p[3] != 0).count();
                serde_json::json!({"label":label,"id":id,"width":data.width,
                    "height":data.height,"visible_pixels":visible})
            }
            None => serde_json::json!({"label":label,"id":null}),
        };
        println!("{result}");
        io::stdout().flush().expect("flush probe result");
    }
}
