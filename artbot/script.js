let canvas = document.querySelector("canvas")
let ctx = canvas.getContext("2d")

function random_choice(choices){
    return choices[Math.floor(Math.random()*choices.length)]
}

function random_value(max){
    return Math.floor(Math.random()*max)
}

function random_shape(){
    let x = random_value(canvas.height)
    let y = random_value(canvas.width)
    let w = random_value(20)
    let h = random_value(20)
    let color = random_choice(["blue","orange","red","white","black"])
    ctx.fillStyle = color
    ctx.fillRect(x,y,w,h)
}

for(i=0;i<10000;i++){
    random_shape()
}
