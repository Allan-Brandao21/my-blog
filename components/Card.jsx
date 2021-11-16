import styles from '../styles/Card.module.css'
import Link from 'next/link'

const Card = ({post}) => {
    return (
            <div key={post.uid} className={styles.card}>
            <Link href={`/${post.uid}`}>
                <a>
            <h2 className={styles.title}>{post.data.title[0].text}</h2>
            {
              post.data.description.map(content => (
                <p key={Math.random()} className={styles.description}>{content.text}</p>
              ))
            }
            </a>
            </Link>
          
          </div>
    )
}


export default Card